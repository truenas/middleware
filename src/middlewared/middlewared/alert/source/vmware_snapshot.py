import pickle as pickle

from lockfile import LockFile

from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource

VMWARE_FAILS = "/var/tmp/.vmwaresnap_fails"
VMWARESNAPDELETE_FAILS = "/var/tmp/.vmwaresnapdelete_fails"


class VMWareSnapshotCreateFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "Creating VMWare Snapshot Failed"
    text = "Creating VMWare snapshot %(snapshot)s of VM %(vm)s at %(hostname)s failed: %(error)s."

    deleted_automatically = False

    async def create(self, args):
        return Alert(VMWareSnapshotCreateFailedAlertClass, args)

    async def delete(self, alerts, query):
        pass


class VMWareSnapshotDeleteFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "VMWare Snapshot Deletion Failed"
    text = "Deletion of VMWare snapshot %(snapshot)s of VM %(vm)s on %(hostname)s failed: %(error)s."

    deleted_automatically = False

    async def create(self, args):
        return Alert(VMWareSnapshotDeleteFailedAlertClass, args)

    async def delete(self, alerts, query):
        pass


class LegacyVMWareSnapshotFailedAlertSource(ThreadedAlertSource):
    def check_sync(self):
        try:
            with LockFile(VMWARE_FAILS):
                with open(VMWARE_FAILS, "rb") as f:
                    fails = pickle.load(f)
        except Exception:
            return

        alerts = []
        for snapname, vms in list(fails.items()):
            for vm in vms:
                alerts.append(Alert(
                    VMWareSnapshotCreateFailedAlertClass,
                    {
                        "snapshot": snapname,
                        "vm": vm,
                        "hostname": "<hostname>",
                        "error": "Error",
                    }
                ))
        return alerts


class LegacyVMWareSnapshotDeleteFailAlertSource(ThreadedAlertSource):
    def check_sync(self):
        try:
            with LockFile(VMWARESNAPDELETE_FAILS):
                with open(VMWARESNAPDELETE_FAILS, "rb") as f:
                    fails = pickle.load(f)
        except Exception:
            return

        alerts = []
        for snapname, vms in list(fails.items()):
            for vm in vms:
                alerts.append(Alert(
                    VMWareSnapshotDeleteFailedAlertClass,
                    {
                        "snapshot": snapname,
                        "vm": vm,
                        "hostname": "<hostname>",
                        "error": "Error",
                    }
                ))

        return alerts
