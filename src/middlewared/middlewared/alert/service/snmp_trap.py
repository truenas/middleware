import pysnmp.hlapi
import pysnmp.smi

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict


class SNMPTrapAlertService(ThreadedAlertService):
    title = "SNMP Trap"

    schema = Dict(
        "snmp_attributes",
    )

    def __init__(self, middleware, attributes):
        super().__init__(middleware, attributes)

        self.initialized = False

    def send_sync(self, alerts, gone_alerts, new_alerts):
        if not self.middleware.call_sync("service.started", "snmp"):
            self.logger.trace("SNMP service not started, not sending traps")
            return

        if not self.initialized:
            self.snmp_engine = pysnmp.hlapi.SnmpEngine()
            self.auth_data = pysnmp.hlapi.CommunityData("public")
            self.transport_target = pysnmp.hlapi.UdpTransportTarget(("localhost", 162))
            self.context_data = pysnmp.hlapi.ContextData()

            mib_builder = pysnmp.smi.builder.MibBuilder()
            mib_sources = mib_builder.getMibSources() + (
                pysnmp.smi.builder.DirMibSource("/usr/local/share/pysnmp/mibs"),)
            mib_builder.setMibSources(*mib_sources)
            mib_builder.loadModules("FREENAS-MIB")
            self.snmp_alert_level_type = mib_builder.importSymbols("FREENAS-MIB", "AlertLevelType")[0]
            mib_view_controller = pysnmp.smi.view.MibViewController(mib_builder)
            self.snmp_alert = pysnmp.hlapi.ObjectIdentity("FREENAS-MIB", "alert"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_id = pysnmp.hlapi.ObjectIdentity("FREENAS-MIB", "alertId"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_level = pysnmp.hlapi.ObjectIdentity("FREENAS-MIB", "alertLevel"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_message = pysnmp.hlapi.ObjectIdentity("FREENAS-MIB", "alertMessage"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_cancellation = pysnmp.hlapi.ObjectIdentity("FREENAS-MIB", "alertCancellation"). \
                resolveWithMib(mib_view_controller)

            self.initialized = True

        for alert in gone_alerts:
            error_indication, error_status, error_index, var_binds = next(
                pysnmp.hlapi.sendNotification(
                    self.snmp_engine,
                    self.auth_data,
                    self.transport_target,
                    self.context_data,
                    "trap",
                    pysnmp.hlapi.NotificationType(self.snmp_alert_cancellation).addVarBinds(
                        (pysnmp.hlapi.ObjectIdentifier(self.snmp_alert_id),
                         pysnmp.hlapi.OctetString(self._alert_id(alert)))
                    )
                )
            )

            if error_indication:
                self.logger.error(f"Failed to send SNMP trap: %s", error_indication)

        for alert in new_alerts:
            error_indication, error_status, error_index, var_binds = next(
                pysnmp.hlapi.sendNotification(
                    self.snmp_engine,
                    self.auth_data,
                    self.transport_target,
                    self.context_data,
                    "trap",
                    pysnmp.hlapi.NotificationType(self.snmp_alert).addVarBinds(
                        (pysnmp.hlapi.ObjectIdentifier(self.snmp_alert_id),
                         pysnmp.hlapi.OctetString(self._alert_id(alert))),
                        (pysnmp.hlapi.ObjectIdentifier(self.snmp_alert_level),
                         self.snmp_alert_level_type(
                             self.snmp_alert_level_type.namedValues.getValue(alert.level_name.lower()))),
                        (pysnmp.hlapi.ObjectIdentifier(self.snmp_alert_message),
                         pysnmp.hlapi.OctetString(alert.formatted))
                    )
                )
            )

            if error_indication:
                self.logger.warning(f"Failed to send SNMP trap: %s", error_indication)

    def _alert_id(self, alert):
        return f"{alert.source};{alert.key}"
