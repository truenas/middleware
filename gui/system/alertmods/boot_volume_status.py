import re
import subprocess

from django.utils.translation import ugettext as _
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.middleware.notifier import notifier

class BootVolumeStatusAlert(BaseAlert):

    __metaclass__ = HookMetaclass
    __hook_reverse_order__ = False
    name = 'BootVolumeStatus'
    
    def on_volume_status_not_healthy(self, status, message):
        if message:
            return Alert(
                Alert.WARN,
                _('The boot volume status is %(status)s:'
                  ' %(message)s') % {
                    'status': status,
                    'message': message,
                }
            )
        else:
            return Alert(
                Alert.WARN,
                _('The boot volume status is %(status)s') % {
                    'status': status,
                }
            )

    def run(self):
        alerts = []
        status, message = notifier().boot_zpool_status()
        
        if status == 'HEALTHY':
            #alerts.append(Alert(
            #    Alert.OK, _('The boot volume status is HEALTHY')
            #))
            # Do not alert the user and then state all is well!
            pass
        elif status == 'DEGRADED':
             alerts.append(Alert(Alert.CRIT,_('The boot volume status is DEGRADED')))
        else:
            alerts.append(
                self.on_volume_status_not_healthy(status, message)
            )
        return alerts

alertPlugins.register(BootVolumeStatusAlert)
