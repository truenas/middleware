from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, OneShotAlertClass


class SMBAuditShareDisabledAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    keys = []
    title = "SMB share audit configuration contains invalid groups"
    text = "SMB shares disabled due to invalid group in audit configuration: %(shares)s"
