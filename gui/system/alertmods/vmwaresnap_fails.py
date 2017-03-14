import pickle as pickle

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

from lockfile import LockFile

VMWARE_FAILS = '/var/tmp/.vmwaresnap_fails'


class VMWareSnapFailAlert(BaseAlert):

    def run(self):
        try:
            with LockFile(VMWARE_FAILS) as lock:
                with open(VMWARE_FAILS, 'rb') as f:
                    fails = pickle.load(f)
        except:
            return None

        alerts = []
        for snapname, vms in list(fails.items()):
            alerts.append(Alert(Alert.WARN, _(
                'VMWare snapshot %(snap)s failed for the following VMs: '
                '%(vms)s'
            ) % {
                'snap': snapname,
                'vms': ', '.join(vms),
            }))
        return alerts

alertPlugins.register(VMWareSnapFailAlert)
