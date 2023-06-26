import asyncio
import async_timeout
import os
import subprocess
import time
import math

from middlewared.common.smart.smartctl import SMARTCTL_POWERMODES
from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.disks import get_disks_temperatures, parse_smartctl_for_temperature_output
from middlewared.utils.itertools import grouper


class DiskService(Service):
    cache = {}

    @private
    async def disks_for_temperature_monitoring(self):
        return [
            disk['name']
            for disk in await self.middleware.call(
                'disk.query',
                [
                    ['name', '!=', None],
                    ['togglesmart', '=', True],
                    # Polling for disk temperature does not allow them to go to sleep automatically
                    ['hddstandby', '=', 'ALWAYS ON'],
                ]
            )
        ]

    @accepts(
        Str('name'),
        Dict(
            'options',
            Int('cache', default=None, null=True),
            Str('powermode', enum=SMARTCTL_POWERMODES, default=SMARTCTL_POWERMODES[0]),
        ),
        deprecated=[
            (
                lambda args: len(args) == 2 and isinstance(args[1], str),
                lambda name, powermode: [name, {'powermode': powermode}],
            ),
        ],
    )
    @returns(Int('temperature', null=True))
    async def temperature(self, name, options):
        """
        Returns temperature for device `name` using specified S.M.A.R.T. `powermode`. If `cache` is not null
        then the last cached within `cache` seconds value is used.
        """
        if options['cache'] is not None:
            if cached := self.cache.get(name):
                temperature, cache_time = cached
                if cache_time > time.monotonic() - options['cache']:
                    return temperature

        temperature = await self.middleware.call('disk.temperature_uncached', name, options['powermode'])

        self.cache[name] = (temperature, time.monotonic())
        return temperature

    @private
    async def temperature_uncached(self, name, powermode):
        output = await self.middleware.call('disk.smartctl', name, ['-a', '-n', powermode.lower()], {'silent': True})
        if output is not None:
            return parse_smartctl_for_temperature_output(output)

    @private
    async def reset_temperature_cache(self):
        self.cache = {}

    @accepts(
        List('names', items=[Str('name')]),
        Dict(
            'options',
            # A little less than collectd polling interval of 300 seconds to avoid returning old value when polling
            # occurs in 299.9 seconds.
            Int('cache', default=290, null=True),
            Bool('only_cached', default=False),
            Str('powermode', enum=SMARTCTL_POWERMODES, default=SMARTCTL_POWERMODES[0]),
        ),
        deprecated=[
            (
                lambda args: len(args) == 2 and isinstance(args[1], str),
                lambda name, powermode: [name, {'powermode': powermode}],
            ),
        ],
    )
    @returns(Dict('disks_temperatures', additional_attrs=True))
    async def temperatures(self, names, options):
        """
        Returns temperatures for a list of devices (runs in parallel).
        See `disk.temperature` documentation for more details.
        If `only_cached` is specified then this method only returns disk temperatures that exist in cache.
        """
        if len(names) == 0:
            names = await self.disks_for_temperature_monitoring()

        if options.pop('only_cached'):
            return {
                disk: temperature
                for disk, (temperature, cache_time) in self.cache.items()
                if (
                    disk in names and
                    cache_time > time.monotonic() - 610  # Double collectd polling interval + a little bit
                )
            }

        async def temperature(name):
            try:
                async with async_timeout.timeout(15):
                    return await self.middleware.call('disk.temperature', name, options)
            except asyncio.TimeoutError:
                return None

        return dict(zip(names, await asyncio_map(temperature, names, 8)))

    @private
    def read_temps(self):
        """
        The main consumer of this endpoint is the disktemp.py collectd python plugin
        which polls and calls this method every 300 seconds (5 mins). The way we configure
        the smartd.conf, the temperature will be written to disk in csv file format for each
        drive. However, smartd only supports writing temp information for sata/sas drives at
        the moment. Luckily, the kernel (via the hwmon interface) reports nvme drive temperatures
        (if the nvme drive supports it). This means we can get all drive temperatures quite quickly.
        However, if we can't get a drive temperature using these methods for whatever reason then
        we will fall back to subprocessing out to smartctl and trying to parse the temperature.
        """
        return get_disks_temperatures()

    @private
    def get_temp_value(self, value):
        if math.isnan(value):
            value = None
        return value

    @accepts(List('names', items=[Str('name')]), Int('days'))
    @returns(Dict('temperatures', additional_attrs=True))
    def temperature_agg(self, names, days):
        """
        Returns min/max/avg temperature for `names` disks for the last `days` days.
        """
        disks = []
        args = []
        for name in names:
            path = f'/var/db/collectd/rrd/localhost/disktemp-{name}/temperature.rrd'
            if not os.path.exists(path):
                continue

            disks.append(name)
            for DEF, VDEF in [('MIN', 'MINIMUM'), ('MAX', 'MAXIMUM'), ('AVERAGE', 'AVERAGE')]:
                args.extend([
                    f'DEF:{name}{DEF}=/var/db/collectd/rrd/localhost/disktemp-{name}/temperature.rrd:value:{DEF}',
                    f'VDEF:v{name}{DEF}={name}{DEF},{VDEF}',
                    f'PRINT:v{name}{DEF}:%lf',
                ])

        output = list(map(float, subprocess.run(
            ['rrdtool', 'graph', 'x', '--daemon', 'unix:/var/run/rrdcached.sock', '--start', f'-{days}d', '--end',
             'now'] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding='ascii',
        ).stdout.split()[1:]))  # The first line is `0x0`

        result = {}
        for disk, values in zip(disks, grouper(output, 3)):  # FIXME: `incomplete='strict' when we switch to python 3.10
            result[disk] = {
                'min': self.get_temp_value(values[0]),
                'max': self.get_temp_value(values[1]),
                'avg': self.get_temp_value(values[2]),
            }

        return result

    @accepts(List('names', items=[Str('name')]))
    @returns(Ref('alert'))
    async def temperature_alerts(self, names):
        """
        Returns existing temperature alerts for specified disk `names.`
        """
        devices = {f'/dev/{name}' for name in names}
        alerts = await self.middleware.call('alert.list')
        return [
            alert for alert in alerts
            if (
                alert['klass'] == 'SMART' and
                alert['args']['device'] in devices and
                'temperature' in alert['args']['message'].lower()
            )
        ]
