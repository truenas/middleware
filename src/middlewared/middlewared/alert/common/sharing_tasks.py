from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, OneShotAlertClass


class SharingTaskLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING

    async def get_create_args(self, args):
        raise NotImplementedError

    async def create(self, args):
        args = await self.get_create_args(args)
        return Alert(SharingTaskLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class ShareLockedAlertClass(SharingTaskLockedAlertClass):
    category = AlertCategory.SHARING
    title = 'Share Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s share "%(name)s" is unavailable because it uses a locked dataset.'

    async def get_create_args(self, args):
        return {**args, 'type': self.__class__.__name__.split('ShareLockedAlertClass')[0]}


class TaskLockedAlertClass(SharingTaskLockedAlertClass):
    category = AlertCategory.TASKS
    title = 'Task Is Unavailable Because It Uses A Locked Dataset'
    text = '%(type)s share "%(name)s" will not be executed because it uses a locked dataset.'

    async def get_create_args(self, args):
        return {**args, 'type': self.__class__.__name__.split('TaskLockedAlertClass')[0]}
