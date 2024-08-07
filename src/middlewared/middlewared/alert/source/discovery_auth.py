from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class ISCSIDiscoveryAuthMixedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "iSCSI Discovery Authorization Global"
    text = "Prior to upgrade had specified iSCSI discovery auth on only some portals, now applies globally.  May need to update client configuration when using %(ips)s"


class ISCSIDiscoveryAuthMultipleCHAPAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "iSCSI Discovery Authorization merged"
    text = "Prior to upgrade different portals had different iSCSI discovery auth, now applies globally."


class ISCSIDiscoveryAuthMultipleMutualCHAPAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "iSCSI Discovery Authorization Multiple Mutual CHAP"
    text = "Multiple mutual CHAP peers defined for discovery auth, but only first one (\"%(peeruser)s\") applies.  May need to update client configuration."
