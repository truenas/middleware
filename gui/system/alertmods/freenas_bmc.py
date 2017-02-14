import logging
import re

from django.utils.translation import ugettext as _

from freenasUI.common.pipesubr import pipeopen
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

log = logging.getLogger('FreeNASBMCAlert')


class FreeNASBMCAlert(BaseAlert):

    interval = 60

    def run(self):
        alerts = []
        systemname = pipeopen("/usr/local/sbin/dmidecode -s system-product-name").communicate()[0].strip()
        boardname = pipeopen("/usr/local/sbin/dmidecode -s baseboard-product-name").communicate()[0].strip()
        if 'freenas' in systemname.lower() and boardname == 'C2750D4I':
            mcinfo = pipeopen("/usr/local/bin/ipmitool mc info").communicate()[0]
            reg = re.search(r'Firmware Revision.*: (\S+)', mcinfo, flags=re.M)
            if not reg:
                return alerts
            fwver = reg.group(1)
            try:
                fwver = [int(i) for i in fwver.split('.')]
            except ValueError:
                log.warn('Failed to parse BMC firmware version: {}'.format(fwver))
                return alerts

            if len(fwver) < 2 or not(fwver[0] == 0 and fwver[1] < 30):
                return alerts

            alerts.append(
                Alert(
                    Alert.CRIT,
                    _(
                        'FreeNAS Mini Critical IPMI Firmware Update - Your '
                        'Mini has an available IPMI firmware update, please '
                        'click <a href="%s" target="_blank">here</a> for '
                        'installation instructions'
                    ) % 'https://support.ixsystems.com/index.php?/Knowledgebase/Article/View/287',
                )
            )
        return alerts


alertPlugins.register(FreeNASBMCAlert)
