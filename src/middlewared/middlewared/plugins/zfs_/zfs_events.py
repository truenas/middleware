import asyncio
from collections import defaultdict
import libzfs
import threading
import time

from middlewared.alert.base import (
    Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass, SimpleOneShotAlertClass
)
from middlewared.utils import osc, start_daemon_thread

CACHE_POOLS_STATUSES = 'system.system_health_pools'

SCAN_THREADS = {}


class ScanWatch(object):

    def __init__(self, middleware, pool):
        self.middleware = middleware
        self.pool = pool
        self._cancel = threading.Event()

    def run(self):
        while not self._cancel.wait(2):
            with libzfs.ZFS() as zfs:
                scan = zfs.get(self.pool).scrub.__getstate__()
            if scan['state'] == 'SCANNING':
                self.send_scan(scan)
            elif scan['state'] == 'FINISHED':
                # Since this thread finishes on scrub/resilver end the event is sent
                # on devd event arrival
                break

    def send_scan(self, scan=None):
        if not scan:
            with libzfs.ZFS() as zfs:
                scan = zfs.get(self.pool).scrub.__getstate__()
        self.middleware.send_event('zfs.pool.scan', 'CHANGED', fields={
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
    text = "Scrub of pool %r started."

    deleted_automatically = False


class ScrubFinishedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.INFO
    title = "Scrub Finished"
    text = "Scrub of pool %r finished."

    deleted_automatically = False


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
    await middleware.call('alert.oneshot_delete', 'ScrubFinished', pool_name)
    await middleware.call('alert.oneshot_create', 'ScrubFinished', pool_name)


async def devd_zfs_hook(middleware, data):
    if data.get('type') in (
        'ATTACH',
        'DETACH',
        'resource.fs.zfs.removed',
        'sysevent.fs.zfs.config_sync',
    ):
        asyncio.ensure_future(middleware.call('pool.sync_encrypted'))

deadman_throttle = defaultdict(list)


async def retrieve_pool_from_db(middleware, pool_name):
    pool = await middleware.call('pool.query', [['name', '=', pool_name]])
    if not pool:
        # If we have no record of the pool, let's skip sending any event please
        return
    return pool[0]


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
    elif event_id == 'ereport.fs.zfs.deadman':
        vdev = data.get('vdev_path', '<unknown>')
        pool = data.get('pool', '<unknown>')
        now = time.monotonic()
        interval = 300
        max_items = 5
        deadman_throttle[pool] = list(filter(lambda t: t > now - interval, deadman_throttle[pool]))
        if len(deadman_throttle[pool]) < max_items:
            asyncio.ensure_future(middleware.call('alert.oneshot_create', 'ZfsDeadman', {
                'vdev': vdev,
                'pool': pool,
            }))
        deadman_throttle[pool].append(now)
        deadman_throttle[pool] = deadman_throttle[pool][-max_items:]
    elif event_id == 'resource.fs.zfs.statechange':
        await middleware.call('cache.pop', CACHE_POOLS_STATUSES)
        pool = await retrieve_pool_from_db(middleware, data.get('pool'))
        if not pool:
            return

        middleware.send_event('pool.query', 'CHANGED', id=pool['id'], fields=pool)

    elif event_id in (
        'sysevent.fs.zfs.config_sync',
        'sysevent.fs.zfs.pool_destroy',
        'sysevent.fs.zfs.pool_import',
    ):
        # Swap must be configured only on disks being used by some pool,
        # for this reason we must react to certain types of ZFS events to keep
        # it in sync every time there is a change.
        asyncio.ensure_future(middleware.call('disk.swaps_configure'))
        if event_id == 'sysevent.fs.zfs.config_sync' and data.get('pool') and data.get('pool_guid'):
            # This event is issued whenever a vdev change is done to a pool
            # Checking pool_guid ensures that we do not do this on creation/deletion of pool as we expect the
            # relevant event to be handled from the service endpoints because there are other operations related
            # to create/delete which when done, we consider the create/delete operation as complete
            pool = await retrieve_pool_from_db(middleware, data['pool'])
            if not pool:
                return

            middleware.send_event('pool.query', 'CHANGED', id=pool['id'], fields=pool)
    elif (
        event_id == 'sysevent.fs.zfs.history_event' and data.get('history_dsname') and data.get('history_internal_name')
    ):
        # we need to send events for dataset creation/updating/deletion in case it's done via cli
        event_type = data['history_internal_name']
        ds_id = data['history_dsname']
        if await middleware.call('pool.dataset.is_internal_dataset', ds_id):
            # We should not raise any event for system internal datasets
            return

        if event_type in ('create', 'set'):
            ds_data = await middleware.call('pool.dataset.query', [['id', '=', ds_id]])
            if not ds_data:
                # We should not send an event because of 2 reasons:
                # 1) Dataset in question was system dataset which was filtered out by pool.dataset service
                # 2) Dataset got deleted in a race condition which is still fine as destroy event will catch that
                return

            ds_data = ds_data[0]
            middleware.send_event(
                'pool.dataset.query', 'ADDED' if event_type == 'create' else 'CHANGED', id=ds_id, fields=ds_data
            )
        elif event_type == 'destroy':
            middleware.send_event('pool.dataset.query', 'CHANGED', id=ds_id, cleared=True)

            await middleware.call(
                'pool.dataset.delete_encrypted_datasets_from_db', [
                    ['OR', [['name', '=', data['history_dsname']], ['name', '^', f'{data["history_dsname"]}/']]]
                ]
            )
            await middleware.call_hook('dataset.post_delete', data['history_dsname'])


def setup(middleware):
    middleware.event_register('zfs.pool.scan', 'Progress of pool resilver/scrub.')
    middleware.register_hook('zfs.pool.events', zfs_events, sync=False)
    if osc.IS_FREEBSD:
        middleware.register_hook('devd.zfs', devd_zfs_hook)
