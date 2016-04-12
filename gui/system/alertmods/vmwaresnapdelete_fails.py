import cPickle as pickle

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert

from lockfile import LockFile

VMWARESNAPDELETE_FAILS = '/var/tmp/.vmwaresnapdelete_fails'


class VMWareSnapDeleteFailAlert(BaseAlert):

    def run(self):
        try:
            with LockFile(VMWARESNAPDELETE_FAILS) as lock:
                with open(VMWARESNAPDELETE_FAILS, 'rb') as f:
                    fails = pickle.load(f)
        except:
            return None

        alerts = []
        for snapname, vms in fails.items():
            alerts.append(Alert(Alert.WARN, _(
                'VMWare snapshot deletion %(snap)s failed for the following VMs: '
                '%(vms)s'
            ) % {
                'snap': snapname,
                'vms': ', '.join(vms),
            }))
        return alerts

alertPlugins.register(VMWareSnapDeleteFailAlert)
