import os

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

PORTAL_IP_FILE = '/var/tmp/iscsi_portal_ip'


class PortalIPAlert(BaseAlert):

    def run(self):
        if not os.path.exists(PORTAL_IP_FILE):
            return None
        with open(PORTAL_IP_FILE) as f:
            ips = f.read().split('\n')
            ips = [y for y in ips if bool(y)]
            return [
                Alert(
                    Alert.WARN,
                    _('The following IPs are bind to iSCSI Portal but were not'
                      ' found in the system: %s') % (', '.join(ips))
                )
            ]

alertPlugins.register(PortalIPAlert)
