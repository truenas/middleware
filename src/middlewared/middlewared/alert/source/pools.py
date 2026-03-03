from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class PoolUpgradedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.NOTICE
    title = "New Feature Flags Are Available for Pool"
    text = (
        "New ZFS version or feature flags are available for pool '%s'. Upgrading pools is a one-time process that can "
        "prevent rolling the system back to an earlier TrueNAS version. It is recommended to read the TrueNAS release "
        "notes and confirm you need the new ZFS feature flags before upgrading a pool."
    )

    async def create(self, args):
        return Alert(PoolUpgradedAlertClass, args, key=args)

    async def delete(self, alerts, query):
        return list(filter(lambda x: x.args != query, alerts))
