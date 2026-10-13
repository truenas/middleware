from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class SyslogNgAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.WARNING
    title = "syslog-ng Is Not Running"
    text = "The syslog-ng service is not running. The system does not record log messages or audit events."


class SyslogNgAlertSource(AlertSource):
    async def check(self):
        if await self.call2(self.s.service.started, "syslogd"):
            return None

        return Alert(SyslogNgAlertClass)
