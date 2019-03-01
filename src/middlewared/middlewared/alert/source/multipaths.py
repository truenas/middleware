from middlewared.alert.base import Alert, AlertLevel, AlertSource


class MultipathsAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Multipath is not optimal"

    hardware = True

    async def check(self):
        return [
            Alert(title="Multipath %s is not optimal",
                  args=[mp['name']])
            for mp in await self.middleware.call("multipath.query")
            if mp['status'] != "OPTIMAL"
        ]
