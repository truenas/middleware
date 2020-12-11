from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class ShareLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SHARING
    title = 'Share Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s share "%(identifier)s" is unavailable because it uses a locked dataset.'

    async def create(self, args):
        return Alert(ShareLockedAlertClass, args, key=f'{args["type"]}_{args["id"]}')

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class TaskLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.TASKS
    title = 'Task Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s task "%(identifier)s" will not be executed because it uses a locked dataset.'

    async def create(self, args):
        return Alert(TaskLockedAlertClass, args, key=f'{args["type"]}_{args["id"]}')

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))
