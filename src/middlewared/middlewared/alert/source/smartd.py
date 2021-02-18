from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class SmartdAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "smartd Is Not Running"
    text = "smartd is not running."


class SmartdAlertSource(ThreadedAlertSource):
    def check_sync(self):
        if self.middleware.call_sync("datastore.query", "services.services", [("srv_service", "=", "smartd"),
                                                                              ("srv_enable", "=", True)]):
            if self.middleware.call_sync("system.vm"):
                return

            if self.middleware.call_sync("system.is_enterprise"):
                if self.middleware.call_sync("failover.status") != "MASTER":
                    return

            if not self.middleware.call_sync("service.started", "smartd"):
                return Alert(SmartdAlertClass)
