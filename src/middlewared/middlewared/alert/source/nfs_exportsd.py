from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class NFSblockedByExportsDirAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.ERROR,
        title="NFS start is blocked by entries in /etc/exports.d",
        text="/etc/exports.d contains entries that must be removed: %(entries)s",
        keys=[],
    )

    entries: str

    @classmethod
    def key(cls, args):
        return None


@dataclass(kw_only=True)
class NFSexportMappingInvalidNamesAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.ERROR,
        title="NFS export entry blocked",
        text="NFS shares have invalid names:\n%(share_list)s",
        keys=[],
    )

    share_list: str

    @classmethod
    def key(cls, args):
        return None
