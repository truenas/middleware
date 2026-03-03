from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class NFSblockedByExportsDirAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.ERROR
    keys = []
    title = "NFS start is blocked by entries in /etc/exports.d"
    text = "/etc/exports.d contains entries that must be removed: %(entries)s"


class NFSexportMappingInvalidNamesAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.ERROR
    keys = []
    title = "NFS export entry blocked"
    text = "NFS shares have invalid names:\n%(share_list)s"
