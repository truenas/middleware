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
