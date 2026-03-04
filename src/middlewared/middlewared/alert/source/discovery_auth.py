from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass

UPGRADE_ALERTS = ['ISCSIDiscoveryAuthMixed', 'ISCSIDiscoveryAuthMultipleCHAP', 'ISCSIDiscoveryAuthMultipleMutualCHAP']


@dataclass(kw_only=True)
class ISCSIDiscoveryAuthMixedAlert(OneShotAlertClass):
    ips: str

    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="iSCSI Discovery Authorization Global",
        text="Prior to upgrade had specified iSCSI discovery auth on only some portals, now applies globally.  May need to update client configuration when using %(ips)s",
    )


class ISCSIDiscoveryAuthMultipleCHAPAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="iSCSI Discovery Authorization merged",
        text="Prior to upgrade different portals had different iSCSI discovery auth, now applies globally.",
    )


@dataclass(kw_only=True)
class ISCSIDiscoveryAuthMultipleMutualCHAPAlert(OneShotAlertClass):
    peeruser: str

    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="iSCSI Discovery Authorization Multiple Mutual CHAP",
        text="Multiple mutual CHAP peers defined for discovery auth, but only first one (\"%(peeruser)s\") applies.  May need to update client configuration.",
    )
