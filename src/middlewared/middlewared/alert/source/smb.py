from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass, Alert


class SMBShareLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'SMB Share Locked'
    text = 'SMB "%(name)s" share operating on a locked resource. Please disable the share.'

    async def create(self, args):
        return Alert(SMBShareLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
