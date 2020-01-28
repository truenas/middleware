import asyncio
import libzfs
import platform
import threading

from middlewared.alert.base import (
    Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass, SimpleOneShotAlertClass
)
from middlewared.utils import start_daemon_thread

CACHE_POOLS_STATUSES = 'system.system_health_pools'
EVENT_LOCK = asyncio.Lock()
IS_LINUX = platform.system().lower() == 'linux'
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
    if data.get('type') in ('misc.fs.zfs.resilver_start', 'misc.fs.zfs.scrub_start'):
        await resilver_scrub_start(middleware, data.get('pool_name'))
    elif data.get('type') in (
        'misc.fs.zfs.resilver_finish', 'misc.fs.zfs.scrub_finish', 'misc.fs.zfs.scrub_abort',
    ):
        await resilver_scrub_stop_abort(middleware, data.get('pool_name'))

    if data.get('type') == 'misc.fs.zfs.scrub_finish':
        await scrub_finished(middleware, data.get('pool_name'))

    if data.get('type') in (
        'ATTACH',
        'DETACH',
        'resource.fs.zfs.removed',
        'misc.fs.zfs.config_sync',
    ):
        asyncio.ensure_future(middleware.call('pool.sync_encrypted'))
    elif data.get('type') == 'ereport.fs.zfs.deadman':
        asyncio.ensure_future(middleware.call('alert.oneshot_create', 'ZfsDeadman', {
            'vdev': data.get('vdev_path', '<unknown>'),
            'pool': data.get('pool', '<unknown>'),
        }))
    elif data.get('type') == 'misc.fs.zfs.vdev_statechange':
        """
        This is so we can invalidate the CACHE_POOLS_STATUSES cache
        when pool status changes
        """
        await middleware.call('cache.pop', CACHE_POOLS_STATUSES)
    elif data.get('type') in (
        'misc.fs.zfs.config_sync',
        'misc.fs.zfs.pool_create',
        'misc.fs.zfs.pool_destroy',
        'misc.fs.zfs.pool_import',
    ):
        # Swap must be configured only on disks being used by some pool,
        # for this reason we must react to certain types of ZFS events to keep
        # it in sync every time there is a change.
        asyncio.ensure_future(middleware.call('disk.swaps_configure'))


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
        asyncio.ensure_future(middleware.call('alert.oneshot_create', 'ZfsDeadman', {
            'vdev': data.get('vdev_path', '<unknown>'),
            'pool': data.get('pool', '<unknown>'),
        }))
    elif event_id == 'resource.fs.zfs.statechange':
        await middleware.call('cache.pop', CACHE_POOLS_STATUSES)
    elif event_id in (
        'sysevent.fs.zfs.config_sync',
        'sysevent.fs.zfs.pool_create',
        'sysevent.fs.zfs.pool_destroy',
        'sysevent.fs.zfs.pool_import',
    ):
        async with EVENT_LOCK:
            await middleware.call('disk.swaps_configure')


def setup(middleware):
    middleware.event_register('zfs.pool.scan', 'Progress of pool resilver/scrub.')
    if IS_LINUX:
        middleware.register_hook('zfs.pool.events', zfs_events, sync=False)
    else:
        middleware.register_hook('devd.zfs', devd_zfs_hook)
