import os

from middlewared.alert.base import Alert, AlertLevel, AlertSource

PORTAL_IP_FILE = "/var/tmp/iscsi_portal_ip"


class iSCSIPortalIPAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "IPs bound to iSCSI Portal were not found in the system"

    async def check(self):
        if os.path.exists(PORTAL_IP_FILE):
            with open(PORTAL_IP_FILE) as f:
                ips = f.read().split("\n")
                ips = [y for y in ips if bool(y)]
                return Alert(
                    "The following IPs are bind to iSCSI Portal but were not found in the system: %s",
                    ", ".join(ips)
                )
