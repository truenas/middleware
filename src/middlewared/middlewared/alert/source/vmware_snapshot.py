import pickle as pickle

from lockfile import LockFile

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

VMWARE_FAILS = "/var/tmp/.vmwaresnap_fails"
VMWARESNAPDELETE_FAILS = "/var/tmp/.vmwaresnapdelete_fails"


class VMWareSnapshotFailedAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare snapshot failed"

    def check_sync(self):
        try:
            with LockFile(VMWARE_FAILS):
                with open(VMWARE_FAILS, "rb") as f:
                    fails = pickle.load(f)
        except Exception:
            return

        alerts = []
        for snapname, vms in list(fails.items()):
            alerts.append(Alert(
                "VMWare snapshot %(snap)s failed for the following VMs: %(vms)s",
                 {
                     "snap": snapname,
                     "vms": ", ".join(vms),
                 }
            ))
        return alerts


class VMWareSnapshotDeleteFailAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare snapshot delete failed"

    def check_sync(self):
        try:
            with LockFile(VMWARESNAPDELETE_FAILS):
                with open(VMWARESNAPDELETE_FAILS, "rb") as f:
                    fails = pickle.load(f)
        except Exception:
            return

        alerts = []
        for snapname, vms in list(fails.items()):
            alerts.append(Alert(
                "VMWare snapshot deletion %(snap)s failed for the following VMs: %(vms)s",
                 {
                     "snap": snapname,
                     "vms": ", ".join(vms),
                 }
            ))
        return alerts
