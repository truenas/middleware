from collections import defaultdict
import sysctl

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class MPRFirmwareAlert(BaseAlert):

    def run(self):
        alerts = []
        mpr = defaultdict(dict)
        for o in sysctl.filter('dev.mpr'):
            mibs = o.name.split('.', 3)
            if len(mibs) < 4:
                continue

            number, mib = mibs[2:4]

            try:
                major = int(o.value.split('.', 1)[0])
                mpr[number][mib] = major
            except:
                continue

        for number, mibs in mpr.items():
            firmware = mibs.get('firmware_version')
            driver = mibs.get('driver_version')
            if firmware != driver:
                alerts.append(Alert(
                    Alert.WARN,
                    _(
                        'Firmware version %(fwversion)s does not match driver '
                        'version %(drversion)s for /dev/mpr%(mpr)s. Please '
                        'flash controller to P%(drversion)s IT firmware.'
                    ) % {
                        'fwversion': firmware,
                        'drversion': driver,
                        'mpr': number,
                    }
                ))

        return alerts

alertPlugins.register(MPRFirmwareAlert)
