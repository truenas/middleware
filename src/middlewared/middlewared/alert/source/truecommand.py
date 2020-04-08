from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class TruecommandConnectionDisabledAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'Truecommand API Key Disabled by iX Portal'
    text = 'Truecommand API Key has been disabled by iX Portal: %(error)s'


class TruecommandConnectionPendingAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = 'Pending Confirmation From iX Portal for Truecommand API Key'
    text = 'Confirmation is pending for Truecommand API Key from iX Portal: %(error)s'


class TruecommandConnectionHealthAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'Truecommand Service Failed Scheduled Health Check'
    text = 'Truecommand service failed scheduled health check, connecting with iX Portal to get details'
