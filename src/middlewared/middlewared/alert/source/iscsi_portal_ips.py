import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource

PORTAL_IP_FILE = "/var/tmp/iscsi_portal_ip"


class ISCSIPortalIPAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "IPs bound to iSCSI Portal were not found in the system"
    text = "The following IPs are bind to iSCSI Portal but were not found in the system: %s"


class ISCSIPortalIPAlertSource(AlertSource):
    async def check(self):
        if os.path.exists(PORTAL_IP_FILE):
            with open(PORTAL_IP_FILE) as f:
                ips = f.read().split("\n")
                ips = [y for y in ips if bool(y)]
                return Alert(ISCSIPortalIPAlertClass, ", ".join(ips))
