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

    async def is_upgraded(self, pool_name):
        try:
            return await self.middleware.call('pool.is_upgraded', pool_name)
        except Exception:
            return

    async def create(self, args):
        pool = args['pool_name']
        if pool == await self.middleware.call('boot.pool_name'):
            # We don't want this alert for the boot pool as it has certain features disabled by design
            return
        if await self.is_upgraded(pool) is False:
            # only alert if it's False explicitly since None means
            # the pool couldn't be found
            return Alert(PoolUpgradedAlertClass, pool, key=pool)

    async def delete(self, alerts, query):
        return list(filter(lambda x: x.args != query, alerts))
