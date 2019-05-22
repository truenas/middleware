from middlewared.alert.base import Alert, AlertLevel, AlertSource


class MultipathsAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Multipath Is Not Optimal"

    hardware = True

    async def check(self):
        return [
            Alert(title="Multipath %s is not optimal. Please check disk cables",
                  args=[mp['name']])
            for mp in await self.middleware.call("multipath.query")
            if mp['status'] != "OPTIMAL"
        ]
