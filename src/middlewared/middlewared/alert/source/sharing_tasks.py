from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass


class ShareLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SHARING
    title = 'Share Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s share "%(identifier)s" is unavailable because it uses a locked dataset.'

    def key(self, args):
        return f'{args["type"]}_{args["id"]}'


class TaskLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.TASKS
    title = 'Task Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s task "%(identifier)s" will not be executed because it uses a locked dataset.'

    def key(self, args):
        return f'{args["type"]}_{args["id"]}'
