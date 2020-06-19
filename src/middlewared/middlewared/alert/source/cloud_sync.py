from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass, Alert


class CloudSyncTaskLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = 'Cloudsync Task Locked'
    text = 'Cloudsync task operating on \"%(path)s\" path is using a locked resource. Please disable the task.'

    async def create(self, args):
        return Alert(CloudSyncTaskLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
