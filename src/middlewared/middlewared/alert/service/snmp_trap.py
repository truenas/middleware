from __future__ import annotations

from typing import Any

import truenas_pysnmp

from middlewared.alert.base import Alert, ThreadedAlertService


class SNMPTrapAlertService(ThreadedAlertService):
    title = "SNMP Trap"

    def send_sync(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        if self.attributes["host"] in ("localhost", "127.0.0.1", "::1"):
            if not self.middleware.call_sync("service.started", "snmp"):
                self.logger.trace("Local SNMP service not started, not sending traps")  # type: ignore[attr-defined]
                return

        auth = {
            "host": self.attributes["host"],
            "port": self.attributes["port"],
            "v3": self.attributes["v3"],
            "community": self.attributes["community"],
            "v3_username": self.attributes["v3_username"],
            "v3_authprotocol": self.attributes["v3_authprotocol"],
            "v3_authkey": self.attributes["v3_authkey"],
            "v3_privprotocol": self.attributes["v3_privprotocol"],
            "v3_privkey": self.attributes["v3_privkey"],
        }

        classes = self.call_sync2(self.s.alertclasses.config).classes

        for alert in gone_alerts:
            try:
                truenas_pysnmp.send_alert_cancellation(**auth, alert_id=alert.uuid)
            except truenas_pysnmp.SNMPError:
                self.logger.error("Failed to send SNMP trap for alert %s", alert.uuid, exc_info=True)

        for alert in new_alerts:
            level = classes.get(alert.instance.config.name, {}).get(  # type: ignore[union-attr,call-overload]
                "level", alert.instance.config.level.name).lower()
            try:
                truenas_pysnmp.send_alert(**auth, alert_id=alert.uuid, level=level, message=alert.formatted)
            except truenas_pysnmp.SNMPError:
                self.logger.warning("Failed to send SNMP trap for alert %s", alert.uuid, exc_info=True)
