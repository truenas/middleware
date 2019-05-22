import pickle as pickle

from lockfile import LockFile

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

VMWARELOGIN_FAILS = "/var/tmp/.vmwarelogin_fails"


class VMWareLoginFailedAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare Login Failed"

    def check_sync(self):
        try:
            with LockFile(VMWARELOGIN_FAILS):
                with open(VMWARELOGIN_FAILS, "rb") as f:
                    fails = pickle.load(f)
        except Exception:
            return

        alerts = []
        for oid, errmsg in list(fails.items()):
            try:
                vmware = self.middleware.call_sync("datastore.query", "storage.vmwareplugin", [["id", "=", oid]],
                                                   {"get": True})
            except IndexError:
                continue

            alerts.append(Alert(
                "VMWare login to %(vmware)s failed: %(err)s",
                {
                    "vmware": vmware["hostname"],
                    "err": errmsg,
                }
            ))

        return alerts
