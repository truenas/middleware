from middlewared.alert.base import AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class TNCHeartbeatConnectionFailureAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TRUENAS_CONNECT,
        level=AlertLevel.ERROR,
        title='Unable to connect to TrueNAS Connect Heartbeat Service',
        text='Failed to connect to TrueNAS Connect Heartbeat Service in the last 48 hours',
        deleted_automatically=False,
        keys=[],
    )


class TNCDisabledAutoUnconfiguredAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TRUENAS_CONNECT,
        level=AlertLevel.ERROR,
        title='TrueNAS Connect Disabled - Service Unconfigured',
        text=(
            'TrueNAS Connect has been disabled from TrueNAS Connect.'
            ' The system has automatically unconfigured itself.'
        ),
        deleted_automatically=False,
        keys=[],
    )
