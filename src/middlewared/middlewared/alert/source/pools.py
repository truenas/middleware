from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class PoolUSBDisksAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = 'Pool consuming USB disks'
    text = '%(pool)r is consuming USB devices %(disks)r which is not recommended.'

    async def get_usb_disks(self, pool_name, disks):
        try:
            return [disk for disk in filter(
                lambda d: d in disks and disks[d]['bus'] == 'USB',
                await self.middleware.call('zfs.pool.get_disks', pool_name)
            )]
        except Exception:
            return []

    async def create(self, args):
        pool_name = args['pool_name']
        disks = args['disks']

        if (usb_disks := await self.get_usb_disks(pool_name, disks)):
            return Alert(PoolUSBDisksAlertClass, {'pool': pool_name, 'disks': ', '.join(usb_disks)}, key=pool_name)

    async def delete(self, alerts, query):
        return list(filter(lambda x: x.key != query, alerts))


class PoolUpgradedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "New Feature Flags Are Available for Pool"
    text = (
        "New ZFS version or feature flags are available for pool '%s'. Upgrading pools is a one-time process that can "
        "prevent rolling the system back to an earlier TrueNAS version. It is recommended to read the TrueNAS release "
        "notes and confirm you need the new ZFS feature flags before upgrading a pool."
    )

    async def is_upgraded(self, pool_name):
        try:
            return await self.middleware.call('zfs.pool.is_upgraded', pool_name)
        except Exception:
            return

    async def create(self, args):
        pool = args['pool_name']
        if await self.is_upgraded(pool) is False:
            # only alert if it's False explicitly since None means
            # the pool couldn't be found
            return Alert(PoolUpgradedAlertClass, pool, key=pool)

    async def delete(self, alerts, query):
        return list(filter(lambda x: x.key != query, alerts))
