from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class TruecommandConnectionDisabledAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'TrueCommand API Key Disabled by iX Portal'
    text = 'TrueCommand API Key has been disabled by iX Portal: %(error)s'


class TruecommandConnectionPendingAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []

    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = 'Pending Confirmation From iX Portal for TrueCommand API Key'
    text = 'Confirmation is pending for TrueCommand API Key from iX Portal: %(error)s'


class TruecommandConnectionHealthAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'TrueCommand Service Failed Scheduled Health Check'
    text = 'TrueCommand service failed scheduled health check, please confirm NAS ' \
           'has been registered with TrueCommand and TrueCommand is able to access NAS.'


class TruecommandContainerHealthAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'TrueCommand Container Failed Scheduled Health Check'
    text = 'TrueCommand container failed scheduled health check, please contact Truecommand support.'
