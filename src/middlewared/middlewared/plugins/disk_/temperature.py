from datetime import datetime, timedelta
from time import time

from middlewared.api import api_method
from middlewared.api.current import (
    DiskTemperatureAggArgs,
    DiskTemperatureAggResult,
    DiskTemperatureAlertsArgs,
    DiskTemperatureAlertsResult,
    DiskTemperaturesArgs,
    DiskTemperaturesResult,
)
from middlewared.service import Service, private
from middlewared.utils.disks_.disk_class import TempEntry

# Alert classes raised per disk by `middlewared.alert.source.disk_temp`.
TEMPERATURE_ALERT_CLASSES = ("DiskTemperatureTooHot", "DiskTemperatureAboveDefaultLimit")


class DiskService(Service):
    temp_cache: dict[str, tuple[TempEntry, float]] = dict()
    temp_cache_age: int = 300  # 5mins

    def __refresh_temp_cache(self):
        """Refresh `temp_cache` for every disk on the system, returning the
        names of the disks that were refreshed."""
        now = time()
        names = list()
        for i in self.middleware.call_sync("disk.get_disks"):
            try:
                temp, temp_time = self.temp_cache[i.name]
                if now - temp_time > self.temp_cache_age:
                    # cache time expired, grab a new temp
                    self.temp_cache[i.name] = (i.temp(), now)
            except KeyError:
                # no cache or disk not in cache
                self.temp_cache[i.name] = (i.temp(), now)

            names.append(i.name)
        return names

    @api_method(
        DiskTemperaturesArgs,
        DiskTemperaturesResult,
        roles=['REPORTING_READ']
    )
    def temperatures(self, names, include_thresholds):
        """
        Returns disk temperatures for disks in degrees celsius.

        .. note::

            Disk temperatures are not retrieved more than once every 5 minutes.
        """
        rv = {i: None for i in names}
        for name in self.__refresh_temp_cache():
            if not names or name in names:
                if include_thresholds:
                    rv[name] = (
                        self.temp_cache[name][0].temp_c,
                        self.temp_cache[name][0].crit,
                    )
                else:
                    rv[name] = self.temp_cache[name][0].temp_c
        return rv

    @private
    def temperature_entries(self, names):
        """Same cache and same 5 minute refresh interval as `temperatures`,
        but returns `(temp_c, crit, max_c)` for each disk.

        This is deliberately not part of the public API: the shape of the
        `disk.temperatures` result is an untyped dict in every released API
        version, so widening its tuple would change the wire format for
        clients pinned to an already frozen version."""
        rv = {i: None for i in names}
        for name in self.__refresh_temp_cache():
            if not names or name in names:
                entry = self.temp_cache[name][0]
                rv[name] = (entry.temp_c, entry.crit, entry.max_c)
        return rv

    @api_method(
        DiskTemperatureAggArgs,
        DiskTemperatureAggResult,
        roles=['REPORTING_READ']
    )
    def temperature_agg(self, names, days):
        """Returns min/max/avg temperature for ``names`` disks over the last ``days`` days."""
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
            name = disk.identifier.split(' | ')[0].strip()
            if name in names and disk.aggregations is not None:
                final[name] = {
                    'min': disk.aggregations.min.get('temperature_value', None),
                    'max': disk.aggregations.max.get('temperature_value', None),
                    'avg': disk.aggregations.mean.get('temperature_value', None),
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
        for i in await self.call2(self.s.alert.list):
            if i.klass in TEMPERATURE_ALERT_CLASSES and i.args["device"] in names:
                alerts.append(i)
        return alerts
