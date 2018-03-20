from middlewared.alert.base import Alert, AlertLevel, AlertSource


class MultipathsAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Multipaths are not optimal"

    hardware = True

    async def check(self):
        not_optimal = []
        for mp in await self.middleware.call("notifier.multipath_all"):
            if mp.status != "OPTIMAL":
                not_optimal.append(mp.name)

        if not_optimal:
            return Alert(
                "The following multipaths are not optimal: %s",
                ", ".join(not_optimal),
            )
