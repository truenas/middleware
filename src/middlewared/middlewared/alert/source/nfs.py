from middlewared.alert.base import (
    AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel, OneShotAlertClass, Alert
)


class NFSBindAddressAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS Services Could Not Bind to Specific IP Addresses, Using 0.0.0.0"
    text = "NFS services could not bind to specific IP addresses, using 0.0.0.0."


class NFSShareLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS Share Locked"
    text = "NFS share operating on \"%(paths)s\" path(s) is using a locked resource. Please disable the share."

    async def create(self, args):
        return Alert(NFSShareLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))

