from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class SharingTaskLockedAbstractAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING

    async def create(self, args):
        return Alert(SharingTaskLockedAbstractAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class ShareLockedAlertClass(SharingTaskLockedAbstractAlertClass):
    category = AlertCategory.SHARING
    title = 'Share Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s share "%(identifier)s" is unavailable because it uses a locked dataset.'


class TaskLockedAlertClass(SharingTaskLockedAbstractAlertClass):
    category = AlertCategory.TASKS
    title = 'Task Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s task "%(identifier)s" will not be executed because it uses a locked dataset.'
