from dataclasses import dataclass

from middlewared.alert.base import AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class TruecommandConnectionDisabledAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title='TrueCommand API Key Disabled by iX Portal',
        text='TrueCommand API Key has been disabled by iX Portal: %(error)s',
        deleted_automatically=False,
        keys=[],
    )

    error: str


@dataclass(kw_only=True)
class TruecommandConnectionPendingAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.INFO,
        title='Pending Confirmation From iX Portal for TrueCommand API Key',
        text='Confirmation is pending for TrueCommand API Key from iX Portal: %(error)s',
        deleted_automatically=False,
        keys=[],
    )

    error: str


class TruecommandConnectionHealthAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title='TrueCommand Service Failed Scheduled Health Check',
        text='TrueCommand service failed scheduled health check, please confirm NAS '
             'has been registered with TrueCommand and TrueCommand is able to access NAS.',
        deleted_automatically=False,
        keys=[],
    )


class TruecommandContainerHealthAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title='TrueCommand Container Failed Scheduled Health Check',
        text='TrueCommand container failed scheduled health check, please contact Truecommand support.',
        deleted_automatically=False,
        keys=[],
    )
