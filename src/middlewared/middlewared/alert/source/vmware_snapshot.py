import pickle as pickle

from lockfile import LockFile

from middlewared.alert.base import Alert, AlertLevel, OneShotAlertSource, ThreadedAlertSource

VMWARE_FAILS = "/var/tmp/.vmwaresnap_fails"
VMWARESNAPDELETE_FAILS = "/var/tmp/.vmwaresnapdelete_fails"


class VMWareSnapshotCreateFailedAlertSource(OneShotAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare snapshot failed"

    async def create(self, args):
        return Alert("Creating VMWare snapshot %(snapshot)s of VM %(vm)s at %(hostname)s failed: %(error)s", args)

    async def delete(self, alerts, query):
        pass


class VMWareSnapshotDeleteFailedAlertSource(OneShotAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare snapshot delete failed"

    async def create(self, args):
        return Alert("Deleting VMWare snapshot %(snapshot)s of VM %(vm)s at %(hostname)s failed: %(error)s", args)

    async def delete(self, alerts, query):
        pass


class LegacyVMWareSnapshotFailedAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare snapshot failed (legacy replication)"

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


class LegacyVMWareSnapshotDeleteFailAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "VMWare snapshot delete failed (legacy replication)"

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
