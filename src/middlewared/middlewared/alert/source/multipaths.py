from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class MultipathIsNotOptimalAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Multipath Connection Is Not Optimal"
    text = "Multipath %s connection is not optimal. Please check disk cables."

    hardware = True


class MultipathsAlertSource(AlertSource):
    async def check(self):
        return [
            Alert(MultipathIsNotOptimalAlertClass, mp['name'])
            for mp in await self.middleware.call("multipath.query")
            if mp['status'] != "OPTIMAL"
        ]
