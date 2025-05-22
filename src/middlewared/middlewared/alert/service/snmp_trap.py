import pysnmp.hlapi
import pysnmp.smi

from middlewared.alert.base import ThreadedAlertService


class SNMPTrapAlertService(ThreadedAlertService):
    title = "SNMP Trap"

    def __init__(self, middleware, attributes):
        super().__init__(middleware, attributes)

        self.initialized = False

    def send_sync(self, alerts, gone_alerts, new_alerts):
        if self.attributes["host"] in ("localhost", "127.0.0.1", "::1"):
            if not self.middleware.call_sync("service.started", "snmp"):
                self.logger.trace("Local SNMP service not started, not sending traps")
                return

        if not self.initialized:
            self.snmp_engine = pysnmp.hlapi.SnmpEngine()
            if self.attributes["v3"]:
                self.auth_data = pysnmp.hlapi.UsmUserData(
                    self.attributes["v3_username"] or "",
                    self.attributes["v3_authkey"],
                    self.attributes["v3_privkey"],
                    {
                        None: pysnmp.hlapi.usmNoAuthProtocol,
                        "MD5": pysnmp.hlapi.usmHMACMD5AuthProtocol,
                        "SHA": pysnmp.hlapi.usmHMACSHAAuthProtocol,
                        "128SHA224": pysnmp.hlapi.usmHMAC128SHA224AuthProtocol,
                        "192SHA256": pysnmp.hlapi.usmHMAC192SHA256AuthProtocol,
                        "256SHA384": pysnmp.hlapi.usmHMAC256SHA384AuthProtocol,
                        "384SHA512": pysnmp.hlapi.usmHMAC384SHA512AuthProtocol,
                    }[self.attributes["v3_authprotocol"]],
                    {
                        None: pysnmp.hlapi.usmNoPrivProtocol,
                        "DES": pysnmp.hlapi.usmDESPrivProtocol,
                        "3DESEDE": pysnmp.hlapi.usm3DESEDEPrivProtocol,
                        "AESCFB128": pysnmp.hlapi.usmAesCfb128Protocol,
                        "AESCFB192": pysnmp.hlapi.usmAesCfb192Protocol,
                        "AESCFB256": pysnmp.hlapi.usmAesCfb256Protocol,
                        "AESBLUMENTHALCFB192": pysnmp.hlapi.usmAesBlumenthalCfb192Protocol,
                        "AESBLUMENTHALCFB256": pysnmp.hlapi.usmAesBlumenthalCfb256Protocol,
                    }[self.attributes["v3_privprotocol"]],
                )
            else:
                self.auth_data = pysnmp.hlapi.CommunityData(self.attributes["community"])
            self.transport_target = pysnmp.hlapi.UdpTransportTarget((self.attributes["host"], self.attributes["port"]))
            self.context_data = pysnmp.hlapi.ContextData()

            mib_builder = pysnmp.smi.builder.MibBuilder()
            mib_sources = mib_builder.getMibSources() + (
                pysnmp.smi.builder.DirMibSource("/usr/local/share/pysnmp/mibs"),)
            mib_builder.setMibSources(*mib_sources)
            mib_builder.loadModules("TRUENAS-MIB")
            self.snmp_alert_level_type = mib_builder.importSymbols("TRUENAS-MIB", "AlertLevelType")[0]
            mib_view_controller = pysnmp.smi.view.MibViewController(mib_builder)
            self.snmp_alert = pysnmp.hlapi.ObjectIdentity("TRUENAS-MIB", "alert"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_id = pysnmp.hlapi.ObjectIdentity("TRUENAS-MIB", "alertId"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_level = pysnmp.hlapi.ObjectIdentity("TRUENAS-MIB", "alertLevel"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_message = pysnmp.hlapi.ObjectIdentity("TRUENAS-MIB", "alertMessage"). \
                resolveWithMib(mib_view_controller)
            self.snmp_alert_cancellation = pysnmp.hlapi.ObjectIdentity("TRUENAS-MIB", "alertCancellation"). \
                resolveWithMib(mib_view_controller)

            self.initialized = True

        classes = (self.middleware.call_sync("alertclasses.config"))["classes"]

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
                         pysnmp.hlapi.OctetString(alert.uuid))
                    )
                )
            )

            if error_indication:
                self.logger.error("Failed to send SNMP trap: %s", error_indication)

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
                         pysnmp.hlapi.OctetString(alert.uuid)),
                        (pysnmp.hlapi.ObjectIdentifier(self.snmp_alert_level),
                         self.snmp_alert_level_type(
                             self.snmp_alert_level_type.namedValues.getValue(
                                 classes.get(alert.klass.name, {}).get("level", alert.klass.level.name).lower()))),
                        (pysnmp.hlapi.ObjectIdentifier(self.snmp_alert_message),
                         pysnmp.hlapi.OctetString(alert.formatted))
                    )
                )
            )

            if error_indication:
                self.logger.warning("Failed to send SNMP trap: %s", error_indication)
