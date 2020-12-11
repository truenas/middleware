from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel, Alert


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
