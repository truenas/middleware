from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass


class RsyncSuccessAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = 'Rsync Task Succeeded'
    text = 'Rsync "%(direction)s" task for "%(path)s" succeeded.'

    def key(self, args):
        return args['id']


class RsyncFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.CRITICAL
    title = 'Rsync Task Failed'
    text = 'Rsync "%(direction)s" task for "%(path)s" failed.'

    def key(self, args):
        return args['id']
