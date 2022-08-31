from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import CrontabSchedule


class PoolUSBDisksAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = 'Pool consuming USB disks'
    text = '%(pool)r is consuming USB devices %(disks)r which is not recommended.'


class PoolsVersionAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "New Feature Flags Are Available for Pool(s)"
    text = (
        "New ZFS version or feature flags are available for pool(s) %s. Upgrading pools is a one-time process that can "
        "prevent rolling the system back to an earlier TrueNAS version. It is recommended to read the TrueNAS release "
        "notes and confirm you need the new ZFS feature flags before upgrading a pool."
    )


class PoolsChecksAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)  # every 24 hours
    run_on_backup_node = False

    async def get_usb_disks(self, pool_name, disks):
        return [disk for disk in filter(
            lambda d: d in disks and disks[d]['bus'] == 'USB',
            await self.middleware.call('zfs.pool.get_disks', pool_name)
        )]

    async def check(self):
        alerts = []
        pools_with_usb_disks = {}
        not_upgraded_zpools = []
        disks = await self.middleware.call('device.get_disks')

        for guid, info in (await self.middleware.call('zfs.pool.query_imported_fast')).items():
            pool_name = info['name']
            if (usb_disks := await self.get_usb_disks(pool_name, disks)):
                pools_with_usb_disks[pool_name] = usb_disks

            if not await self.middleware.call('zfs.pool.is_upgraded', pool_name):
                not_upgraded_zpools.append(pool_name)

        for pool, usb in pools_with_usb_disks.items():
            alerts.append(Alert(PoolUSBDisksAlertClass, {'pool': pool, 'disks': ', '.join(usb)}))

        if not_upgraded_zpools:
            alerts.append(Alert(PoolsVersionAlertClass, ', '.join(not_upgraded_zpools)))

        return alerts
