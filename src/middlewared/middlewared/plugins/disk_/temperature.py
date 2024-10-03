import asyncio
import datetime
import time
import json

import async_timeout

from middlewared.api import api_method
from middlewared.api.current import DiskTemperatureAlertsArgs, DiskTemperatureAlertsResult
from middlewared.common.smart.smartctl import SMARTCTL_POWERMODES
from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.disks import parse_smartctl_for_temperature_output


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
        roles=['REPORTING_READ']
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
        if output := await self.middleware.call('disk.smartctl', name, ['-a', '-n', powermode.lower(), '--json=c'], {'silent': True}):
            return parse_smartctl_for_temperature_output(json.loads(output))

    @private
    async def reset_temperature_cache(self):
        self.cache = {}

    temperatures_semaphore = asyncio.BoundedSemaphore(8)

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
        roles=['REPORTING_READ']
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

        return dict(zip(names, await asyncio_map(temperature, names, semaphore=self.temperatures_semaphore)))

    @accepts(List('names', items=[Str('name')]), Int('days', default=7), roles=['REPORTING_READ'])
    @returns(Dict('temperatures', additional_attrs=True))
    def temperature_agg(self, names, days):
        """Returns min/max/avg temperature for `names` disks for the last `days` days"""
        # we only keep 7 days of historical data because we keep per second information
        # which adds up to lots of used disk space quickly depending on the size of the
        # system
        start = datetime.datetime.now()
        end = start + datetime.timedelta(days=min(days, 7))
        opts = {'start': round(start.timestamp()), 'end': round(end.timestamp())}
        final = dict()
        for disk in self.middleware.call_sync('reporting.netdata_graph', 'disktemp', opts):
            if disk['identifier'] in names:
                final[disk['identifier']] = {
                    'min': disk['aggregations']['min'].get('temperature_value', None),
                    'max': disk['aggregations']['max'].get('temperature_value', None),
                    'avg': disk['aggregations']['mean'].get('temperature_value', None),
                }

        return final

    @api_method(DiskTemperatureAlertsArgs, DiskTemperatureAlertsResult, roles=['REPORTING_READ'])
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
