import libzfs
import threading

from middlewared.alert.base import (
    Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass, SimpleOneShotAlertClass
)
from middlewared.utils import start_daemon_thread

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


async def devd_zfs_hook(middleware, data):
    if data.get('type') in ('misc.fs.zfs.resilver_start', 'misc.fs.zfs.scrub_start'):
        pool = data.get('pool_name')
        if not pool:
            return
        if pool in SCAN_THREADS:
            return
        scanwatch = ScanWatch(middleware, pool)
        SCAN_THREADS[pool] = scanwatch
        start_daemon_thread(target=scanwatch.run)

    elif data.get('type') in (
        'misc.fs.zfs.resilver_finish', 'misc.fs.zfs.scrub_finish', 'misc.fs.zfs.scrub_abort',
    ):
        pool = data.get('pool_name')
        if not pool:
            return
        scanwatch = SCAN_THREADS.pop(pool, None)
        if not scanwatch:
            return
        await middleware.run_in_thread(scanwatch.cancel)

        # Send the last event with SCRUB/RESILVER as FINISHED
        await middleware.run_in_thread(scanwatch.send_scan)

    if data.get('type') == 'misc.fs.zfs.scrub_finish':
        await middleware.call('alert.oneshot_delete', 'ScrubFinished', data.get('pool_name'))
        await middleware.call('alert.oneshot_create', 'ScrubFinished', data.get('pool_name'))


def setup(middleware):
    middleware.event_register('zfs.pool.scan', 'Progress of pool resilver/scrub.')
    middleware.register_hook('devd.zfs', devd_zfs_hook)
