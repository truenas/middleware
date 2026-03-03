from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class ShareLockedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title='Share Is Unavailable Because It Uses A Locked Dataset',
        text='%(type)s share "%(identifier)s" is unavailable because it uses a locked dataset.',
        deleted_automatically=False,
    )

    @classmethod
    def key(cls, args):
        return f'{args["type"]}_{args["id"]}'


class TaskLockedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.WARNING,
        title='Task Is Unavailable Because It Uses A Locked Dataset',
        text='%(type)s task "%(identifier)s" will not be executed because it uses a locked dataset.',
        deleted_automatically=False,
    )

    @classmethod
    def key(cls, args):
        return f'{args["type"]}_{args["id"]}'
