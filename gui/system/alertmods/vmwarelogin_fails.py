import pickle as pickle

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.storage.models import VMWarePlugin

from lockfile import LockFile

VMWARELOGIN_FAILS = '/var/tmp/.vmwarelogin_fails'


class VMWareLoginFailAlert(BaseAlert):

    def run(self):
        try:
            with LockFile(VMWARELOGIN_FAILS) as lock:
                with open(VMWARELOGIN_FAILS, 'rb') as f:
                    fails = pickle.load(f)
        except:
            return None

        alerts = []
        for oid, errmsg in list(fails.items()):
            vmware = VMWarePlugin.objects.filter(id=oid)
            if not vmware.exists():
                continue
            vmware = vmware[0]
            alerts.append(Alert(Alert.WARN, _(
                'VMWare %(vmware)s failed to login to snapshot: %(err)s' % {
                    'vmware': vmware,
                    'err': errmsg,
                }
            )))
        return alerts


alertPlugins.register(VMWareLoginFailAlert)
