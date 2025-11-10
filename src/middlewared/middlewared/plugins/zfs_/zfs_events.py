import asyncio
from collections import defaultdict
import threading

import libzfs

from middlewared.alert.base import (
    Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass, SimpleOneShotAlertClass
)
from middlewared.utils.threading import start_daemon_thread
from middlewared.utils.zfs import query_imported_fast_impl

CACHE_POOLS_STATUSES = 'system.system_health_pools'

SCAN_THREADS = {}


class ScanWatch:

    def __init__(self, middleware, pool):
        self.middleware = middleware
        self.pool = pool
        self._cancel = threading.Event()

    def run(self):
        while not self._cancel.wait(2):
            with libzfs.ZFS() as zfs:
                scan = zfs.get(self.pool).scrub.asdict()
            if scan['state'] == 'SCANNING':
                self.send_scan(scan)
            elif scan['state'] == 'FINISHED':
                # Since this thread finishes on scrub/resilver end the event is sent
                # on devd event arrival
                break

    def send_scan(self, scan=None):
        if not scan:
            with libzfs.ZFS() as zfs:
                scan = zfs.get(self.pool).scrub.asdict()

        self.middleware.send_event('pool.scan', 'CHANGED', fields={
            'scan': scan,
            'name': self.pool,
        })

    def cancel(self):
        self._cancel.set()


class ScrubNotStartedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "Scrub Failed to Start"
    text = "%s."

    deleted_automatically = False

    async def create(self, args):
        return Alert(self.__class__, args["text"], _key=args["pool"])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != query,
            alerts
        ))


class ScrubStartedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = "Scrub Started"
    text = "Scrub of pool %r has started. Performance may be degraded during this time."


async def resilver_scrub_start(middleware, pool_name):
    if not pool_name:
        return
    if pool_name in SCAN_THREADS:
        return
    scanwatch = ScanWatch(middleware, pool_name)
    SCAN_THREADS[pool_name] = scanwatch
    start_daemon_thread(target=scanwatch.run)


async def resilver_scrub_stop_abort(middleware, pool_name):
    if not pool_name:
        return
    scanwatch = SCAN_THREADS.pop(pool_name, None)
    if not scanwatch:
        return
    await middleware.run_in_thread(scanwatch.cancel)

    # Send the last event with SCRUB/RESILVER as FINISHED
    await middleware.run_in_thread(scanwatch.send_scan)


async def scrub_finished(middleware, pool_name):
    await middleware.call('alert.oneshot_delete', 'ScrubStarted', pool_name)


async def retrieve_pool_from_db(middleware, pool_name):
    pool = await middleware.call('pool.query', [['name', '=', pool_name]])
    if not pool:
        # If we have no record of the pool, let's skip sending any event please
        return
    return pool[0]


POOL_ALERTS = ('PoolUSBDisks', 'PoolUpgraded')
POOL_ALERTS_LOCKS = defaultdict(asyncio.Lock)


async def pool_alerts_args(middleware, pool_name):
    disks = await middleware.call('device.get_disks')
    return {'pool_name': pool_name, 'disks': disks}


async def zfs_events(middleware, data):
    event_id = data['class']
    if event_id in ('sysevent.fs.zfs.resilver_start', 'sysevent.fs.zfs.scrub_start'):
        await resilver_scrub_start(middleware, data.get('pool'))
    elif event_id in (
        'sysevent.fs.zfs.resilver_finish', 'sysevent.fs.zfs.scrub_finish', 'sysevent.fs.zfs.scrub_abort'
    ):
        await resilver_scrub_stop_abort(middleware, data.get('pool'))

    if event_id == 'sysevent.fs.zfs.scrub_finish':
        await scrub_finished(middleware, data.get('pool'))
    elif event_id == 'resource.fs.zfs.statechange':
        await middleware.call('cache.pop', CACHE_POOLS_STATUSES)
        pool = await retrieve_pool_from_db(middleware, data.get('pool'))
        if not pool:
            return
        middleware.send_event('pool.query', 'CHANGED', id=pool['id'], fields=pool)
    elif event_id in (
        'ereport.fs.zfs.checksum',
        'ereport.fs.zfs.io',
        'ereport.fs.zfs.data',
        'ereport.fs.zfs.vdev.clear',
    ):
        await middleware.call('cache.pop', 'VolumeStatusAlerts')
    elif event_id in (
        'sysevent.fs.zfs.config_sync',
        'sysevent.fs.zfs.pool_destroy',
        'sysevent.fs.zfs.pool_import',
    ):
        pool_name = data.get('pool')
        pool_guid = data.get('guid')

        if pool_name:
            await middleware.call('cache.pop', 'VolumeStatusAlerts')

            if pool_name == await middleware.call('boot.pool_name'):
                # a change was made to the boot drive, so let's clear
                # the disk mapping for this pool
                await middleware.call('boot.clear_disks_cache')

            args = await pool_alerts_args(middleware, pool_name)
            async with POOL_ALERTS_LOCKS[pool_name]:
                # The hook is registered with `sync=False` so this code might get executed concurrently for the same
                # `pool_name` if many ZFS events arrive at the same time. This will lead to deletions being scheduled
                # out of order with re-creations.
                if event_id.endswith('pool_import'):
                    for i in POOL_ALERTS:
                        await middleware.call('alert.oneshot_delete', i, pool_name)
                        await middleware.call('alert.oneshot_create', i, args)
                elif event_id.endswith('pool_destroy'):
                    for i in POOL_ALERTS:
                        await middleware.call('alert.oneshot_delete', i, pool_name)
                elif event_id.endswith('config_sync'):
                    if pool_guid and (pool := await retrieve_pool_from_db(middleware, pool_name)):
                        # This event is issued whenever a vdev change is done to a pool
                        # Checking pool_guid ensures that we do not do this on creation/deletion
                        # of pool as we expect the relevant event to be handled from the service
                        # endpoints because there are other operations related to create/delete
                        # which when done, we consider the create/delete operation as complete
                        middleware.send_event('pool.query', 'CHANGED', id=pool['id'], fields=pool)

                    for i in POOL_ALERTS:
                        await middleware.call('alert.oneshot_delete', i, pool_name)
                        await middleware.call('alert.oneshot_create', i, args)
    elif (
        event_id == 'sysevent.fs.zfs.history_event' and data.get('history_dsname') and data.get('history_internal_name')
    ):
        # we need to send events for dataset creation/updating/deletion in case it's done via cli
        event_type = data['history_internal_name']
        ds_id = data['history_dsname']
        if await middleware.call('pool.dataset.is_internal_dataset', ds_id):
            # We should not raise any event for system internal datasets
            return

        # We are not handling create/changed events because it takes a toll on middleware when we are replicating
        # datasets and repeated calls to the process pool can result in tasks getting blocked for longer periods
        # of time and middleware itself getting slow as well to process requests in a timely manner
        # We are now handling create/changed events whenever changes are made via our API
        if event_type == 'destroy':
            if ds_id.split('/')[-1].startswith('%'):
                # Ignore deletion of hidden clones such as `%recv` dataset created by replication
                return

            middleware.send_event('pool.dataset.query', 'REMOVED', id=ds_id)

            await middleware.call(
                'pool.dataset.delete_encrypted_datasets_from_db', [
                    ['OR', [['name', '=', data['history_dsname']], ['name', '^', f'{data["history_dsname"]}/']]]
                ]
            )
            await middleware.call_hook('dataset.post_delete', data['history_dsname'])


async def remove_outdated_alerts_on_boot(middleware, data):
    if data is None:  # Called by `pool.import_on_boot`
        pools = {pool['name'] for pool in (await middleware.run_in_thread(query_imported_fast_impl)).values()}

        for alert in await middleware.call('alert.list'):
            if alert['klass'] == 'PoolUpgraded':
                if alert['args'] not in pools:
                    await middleware.call('alert.oneshot_delete', 'PoolUpgraded', alert['args'])

            if alert['klass'] == 'PoolUSBDisks':
                if alert['args']['pool'] not in pools:
                    await middleware.call('alert.oneshot_delete', 'PoolUSBDisks', alert['args']['pool'])


async def setup(middleware):
    middleware.register_hook('zfs.pool.events', zfs_events, sync=False)

    # middleware does not receive `sysevent.fs.zfs.pool_import` or `sysevent.fs.zfs.config_sync` events on the boot pool
    # import because it happens before middleware is started. We have to manually process these alerts for the boot pool
    pool_name = await middleware.call('boot.pool_name')
    args = await pool_alerts_args(middleware, pool_name)
    for i in POOL_ALERTS:
        await middleware.call('alert.oneshot_delete', i, pool_name)
        await middleware.call('alert.oneshot_create', i, args)

    middleware.register_hook('pool.post_import', remove_outdated_alerts_on_boot)
