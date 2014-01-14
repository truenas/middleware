import re
import subprocess

from django.utils.translation import ugettext_lazy as _

from freenasUI.storage.models import Volume
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class VolumeStatusAlert(BaseAlert):

    def on_volume_status_not_healthy(self, vol, status, message):
        if message:
            return Alert(
                Alert.WARN,
                _('The volume %(volume)s status is %(status)s:'
                  ' %(message)s') % {
                    'volume': vol,
                    'status': status,
                    'message': message,
                }
            )
        else:
            return Alert(
                Alert.WARN,
                _('The volume %(volume)s status is %(status)s') % {
                    'volume': vol,
                    'status': status,
                }
            )

    def volumes_status_enabled(self):
        return True

    def on_volume_status_degraded(self, vol, status, message):
        self.log(self.LOG_CRIT, _('The volume %s status is DEGRADED') % vol)

    def run(self):
        if not self.volumes_status_enabled():
            return
        for vol in Volume.objects.filter(vol_fstype__in=['ZFS', 'UFS']):
            if not vol.is_decrypted():
                continue
            status = vol.status
            message = ""
            if vol.vol_fstype == 'ZFS':
                p1 = subprocess.Popen(
                    ["zpool", "status", "-x", vol.vol_name],
                    stdout=subprocess.PIPE
                )
                stdout = p1.communicate()[0]
                if stdout.find("pool '%s' is healthy" % vol.vol_name) != -1:
                    status = 'HEALTHY'
                else:
                    reg1 = re.search('^\s*state: (\w+)', stdout, re.M)
                    if reg1:
                        status = reg1.group(1)
                    else:
                        # The default case doesn't print out anything helpful,
                        # but instead coredumps ;).
                        status = 'UNKNOWN'
                    reg1 = re.search(r'^\s*status: (.+)\n\s*action+:',
                                     stdout, re.S | re.M)
                    reg2 = re.search(r'^\s*action: ([^:]+)\n\s*\w+:',
                                     stdout, re.S | re.M)
                    if reg1:
                        msg = reg1.group(1)
                        msg = re.sub(r'\s+', ' ', msg)
                        message += msg
                    if reg2:
                        msg = reg2.group(1)
                        msg = re.sub(r'\s+', ' ', msg)
                        message += msg

            if status == 'HEALTHY':
                return [Alert(
                    Alert.OK, _('The volume %s status is HEALTHY') % (vol, )
                )]
            elif status == 'DEGRADED':
                return [self.on_volume_status_degraded(vol, status, message)]
            else:
                return [
                    self.on_volume_status_not_healthy(vol, status, message)
                ]

alertPlugins.register(VolumeStatusAlert)
