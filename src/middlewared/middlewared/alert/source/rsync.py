from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass, Alert


class RsyncSuccessAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = 'Rsync Task Succeeded'
    text = 'Rsync "%(direction)s" task for "%(path)s" succeeded.'

    async def create(self, args):
        return Alert(RsyncSuccessAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))


class RsyncFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.CRITICAL
    title = 'Rsync Task Failed'
    text = 'Rsync "%(direction)s" task for "%(path)s" failed.'

    async def create(self, args):
        return Alert(RsyncFailedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))


class RsyncTaskLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = 'Rsync Task Locked'
    text = 'Rsync task operating on "%(path)s" path is using a locked resource. Please disable the task.'

    async def create(self, args):
        return Alert(RsyncTaskLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))


class RsyncModuleLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = 'Rsync Module Locked'
    text = 'Rsync module "%(name)s"  operating on "%(path)s" path is using a locked ' \
           'resource. Please disable the module.'

    async def create(self, args):
        return Alert(RsyncModuleLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
