from dataclasses import dataclass

from middlewared.alert.base import AlertClass, AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class VMWareSnapshotCreateFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.WARNING,
        title="Creating VMWare Snapshot Failed",
        text="Creating VMWare snapshot %(snapshot)s of VM %(vm)s at %(hostname)s failed: %(error)s.",
        deleted_automatically=False,
        keys=[],
    )

    snapshot: str
    vm: str
    hostname: str
    error: str


@dataclass(kw_only=True)
class VMWareSnapshotDeleteFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.WARNING,
        title="VMWare Snapshot Deletion Failed",
        text="Deletion of VMWare snapshot %(snapshot)s of VM %(vm)s on %(hostname)s failed: %(error)s.",
        deleted_automatically=False,
        keys=[],
    )

    snapshot: str
    vm: str
    hostname: str
    error: str
