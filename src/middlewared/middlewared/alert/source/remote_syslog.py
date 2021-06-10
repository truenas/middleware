from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.utils import run


class RemoteSyslogAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.WARNING
    title = "Remote Syslog Server Is Overloaded"
    text = "Remote syslog server is failing to process sent messages."


class RemoteSyslogAlertSource(AlertSource):
    state = {
        "source": None,
    }

    async def check(self):
        config = await self.middleware.call("system.advanced.config")
        if not config["syslogserver"]:
            return

        source = None
        dropped = None
        written = None
        for line in (
                await run("syslog-ng-ctl", "stats", check=True, encoding="utf-8", errors="ignore")
        ).stdout.splitlines():
            try:
                source_name, source_id, source_instance, state, type, number = line.split(";")
            except ValueError:
                continue

            if source_id == "loghost#0":
                source = source_instance
                if type == "dropped":
                    dropped = int(number)
                if type == "written":
                    written = int(number)

        if source is None or dropped is None or written is None:
            return

        if self.state["source"] != source or dropped < self.state["dropped"] or written < self.state["written"]:
            self.state.update({
                "source": source,
                "dropped": 0,
                "written": 0,
                "has_alert": False,
            })

        has_alert = self.state["has_alert"]
        try:
            if written > self.state["written"]:
                has_alert = False
                return

            if dropped > self.state["dropped"] or self.state["has_alert"]:
                has_alert = True
                return Alert(RemoteSyslogAlertClass)
        finally:
            self.state.update({
                "dropped": dropped,
                "written": written,
                "has_alert": has_alert,
            })
