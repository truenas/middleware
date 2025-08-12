from datetime import datetime, timedelta
from time import time

from middlewared.api import api_method
from middlewared.api.current import (
    DiskTemperaturesArgs,
    DiskTemperaturesResult,
    DiskTemperatureAggArgs,
    DiskTemperatureAggResult,
    DiskTemperatureAlertsArgs,
    DiskTemperatureAlertsResult,
)
from middlewared.service import Service
from middlewared.utils.disks_.disk_class import TempEntry


class DiskService(Service):
    temp_cache: dict[str, tuple[TempEntry, float]] = dict()
    temp_cache_age: int = 300  # 5mins

    @api_method(
        DiskTemperaturesArgs,
        DiskTemperaturesResult,
        roles=['REPORTING_READ']
    )
    def temperatures(self, names, include_thresholds):
        """Returns disk temperatures for disks in degrees celsius.

        NOTE:
            Disk temperatures are not retrieved more than
            once every 5 minutes.
        """
        now = time()
        rv = {i: None for i in names}
        for i in self.middleware.call_sync("disk.get_disks"):
            try:
                temp, temp_time = self.temp_cache[i.name]
                if now - temp_time > self.temp_cache_age:
                    # cache time expired, grab a new temp
                    self.temp_cache[i.name] = (i.temp(), now)
            except KeyError:
                # no cache or disk not in cache
                self.temp_cache[i.name] = (i.temp(), now)

            if not names or i.name in names:
                if include_thresholds:
                    rv[i.name] = (
                        self.temp_cache[i.name][0].temp_c,
                        self.temp_cache[i.name][0].crit,
                    )
                else:
                    rv[i.name] = self.temp_cache[i.name][0].temp_c
        return rv

    @api_method(
        DiskTemperatureAggArgs,
        DiskTemperatureAggResult,
        roles=['REPORTING_READ']
    )
    def temperature_agg(self, names, days):
        """Returns min/max/avg temperature for `names` disks for the last `days` days"""
        # we only keep 7 days of historical data because we keep per second information
        # which adds up to lots of used disk space quickly depending on the size of the
        # system
        end = datetime.now()
        start = end - timedelta(days=min(days, 7))
        opts = {'start': round(start.timestamp()), 'end': round(end.timestamp())}
        final = dict()
        for disk in self.middleware.call_sync('reporting.netdata_graph', 'disktemp', opts):
            # identifier looks like "sda | Type: HDD | Model: HUH721212AL4200 | Serial: aaa"
            # so we need to normalize it before checking if caller has specified it
            name = disk['identifier'].split(' | ')[0].strip()
            if name in names:
                final[name] = {
                    'min': disk['aggregations']['min'].get('temperature_value', None),
                    'max': disk['aggregations']['max'].get('temperature_value', None),
                    'avg': disk['aggregations']['mean'].get('temperature_value', None),
                }
        return final

    @api_method(
        DiskTemperatureAlertsArgs,
        DiskTemperatureAlertsResult,
        roles=['REPORTING_READ']
    )
    async def temperature_alerts(self, names):
        """Returns existing temperature alerts for specified disks."""
        alerts = list()
        names = {f'/dev/{i}' for i in names}
        for i in await self.middleware.call("alert.list"):
            if i["klass"] == "DiskTemperatureTooHot" and i["args"]["device"] in names:
                alerts.append(i)
        return alerts
