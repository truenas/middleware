from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


class TNCHeartbeatConnectionFailureAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TRUENAS_CONNECT,
        level=AlertLevel.ERROR,
        title='Unable to connect to TrueNAS Connect Heartbeat Service',
        text='Failed to connect to TrueNAS Connect Heartbeat Service in the last 7 days',
        deleted_automatically=False,
        keys=[],
    )


class TNCDisabledAutoUnconfiguredAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TRUENAS_CONNECT,
        level=AlertLevel.ERROR,
        title='TrueNAS Connect Unconfigured',
        text=(
            'TrueNAS Connect no longer recognizes this system, so TrueNAS Connect has been automatically'
            ' disabled and unconfigured on this system. Re-register the system with TrueNAS Connect to'
            ' restore access.'
        ),
        deleted_automatically=False,
        keys=[],
    )
