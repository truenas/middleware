from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class RsyncSuccessAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.INFO,
        title='Rsync Task Succeeded',
        text='Rsync "%(direction)s" task for "%(path)s" succeeded.',
        deleted_automatically=False,
    )

    @classmethod
    def key(cls, args):
        return args['id']


class RsyncFailedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title='Rsync Task Failed',
        text='Rsync "%(direction)s" task for "%(path)s" failed.',
        deleted_automatically=False,
    )

    @classmethod
    def key(cls, args):
        return args['id']
