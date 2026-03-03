from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


class NFSblockedByExportsDirAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.ERROR,
        title="NFS start is blocked by entries in /etc/exports.d",
        text="/etc/exports.d contains entries that must be removed: %(entries)s",
        keys=[],
    )


class NFSexportMappingInvalidNamesAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.ERROR,
        title="NFS export entry blocked",
        text="NFS shares have invalid names:\n%(share_list)s",
        keys=[],
    )
