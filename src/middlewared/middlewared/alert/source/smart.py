from middlewared.alert.base import Alert, AlertLevel, OneShotAlertSource


class SMARTAlertSource(OneShotAlertSource):
    level = AlertLevel.CRITICAL
    title = "SMART error"

    hardware = True

    async def create(self, args):
        if not args["device"].startswith("/dev/"):
            args["device"] = f"/dev/{args['device']}"

        return Alert("%(message)s", args)

    async def delete(self, alerts, query):
        device = query

        if not device.startswith("/dev/"):
            device = f"/dev/{device}"

        return list(filter(
            lambda alert: alert.args["device"] != device,
            alerts
        ))
