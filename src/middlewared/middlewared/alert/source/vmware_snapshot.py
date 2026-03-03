from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class VMWareSnapshotCreateFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    keys = []
    title = "Creating VMWare Snapshot Failed"
    text = "Creating VMWare snapshot %(snapshot)s of VM %(vm)s at %(hostname)s failed: %(error)s."

    deleted_automatically = False


class VMWareSnapshotDeleteFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    keys = []
    title = "VMWare Snapshot Deletion Failed"
    text = "Deletion of VMWare snapshot %(snapshot)s of VM %(vm)s on %(hostname)s failed: %(error)s."

    deleted_automatically = False
