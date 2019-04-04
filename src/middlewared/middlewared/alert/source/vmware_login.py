import pickle as pickle

from lockfile import LockFile

from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource

VMWARELOGIN_FAILS = "/var/tmp/.vmwarelogin_fails"


class VMWareLoginFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "VMWare Login Failed"
    text = "VMWare login to %(hostname)s failed: %(error)s."

    async def create(self, args):
        return Alert(VMWareLoginFailedAlertClass, args)

    async def delete(self, alerts, query):
        hostname = query

        return list(filter(
            lambda alert: alert.args["hostname"] != hostname,
            alerts
        ))


class LegacyVMWareLoginFailedAlertSource(ThreadedAlertSource):
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

            alerts.append(Alert(VMWareLoginFailedAlertClass, {
                "hostname": vmware["hostname"],
                "error": errmsg,
            }))

        return alerts
