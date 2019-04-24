from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel, Alert


class SMARTAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "S.M.A.R.T. Error"
    text = "%(message)s."

    hardware = True

    deleted_automatically = False

    async def create(self, args):
        if not args["device"].startswith("/dev/"):
            args["device"] = f"/dev/{args['device']}"

        return Alert(SMARTAlertClass, args)

    async def delete(self, alerts, query):
        device = query

        if not device.startswith("/dev/"):
            device = f"/dev/{device}"

        return list(filter(
            lambda alert: alert.args["device"] != device,
            alerts
        ))
