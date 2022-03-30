import asyncio
import collections
import re


DISKS = ('da', 'ada', 'vtbd', 'mfid', 'nvd', 'pmem')
SHELF = ('ses',)
TYPES = ('CREATE', 'DESTROY')
PREV_TASK = collections.deque(maxlen=1)
MAX_WAIT_TIME = 15
SETTLE_TIME = 5
HAS_PARTITION = re.compile(rf'^({"|".join(DISKS)})[0-9]+p[0-9]+.*$')


async def reset_cache(middleware, *args):
    await middleware.call('geom.cache.invalidate')
    await (await middleware.call('disk.sync_all')).wait()
    await middleware.call('disk.sed_unlock_all')
    PREV_TASK.clear()


async def added_disk(middleware, disk_name):
    await middleware.call('geom.cache.invalidate')
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)
    await middleware.call('disk.multipath_sync')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)
    PREV_TASK.clear()


async def remove_disk(middleware, disk_name):
    await middleware.call('geom.cache.remove_disk', disk_name)
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.multipath_sync')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)
    # If a disk dies we need to reconfigure swaps so we are not left
    # with a single disk mirror swap, which may be a point of failure.
    asyncio.ensure_future(middleware.call('disk.swaps_configure'))
    PREV_TASK.clear()


async def devd_devfs_hook(middleware, data):
    if data.get('subsystem') != 'CDEV' or data['type'] not in TYPES:
        return
    elif not data['cdev'].startswith(DISKS + SHELF):
        return
    elif data['type'] == 'CREATE' and data['cdev'].startswith(DISKS) and HAS_PARTITION.match(data['cdev']):
        # Means we received an event for a disk with a partition already on it (i.e. da1p1).
        # This means we have (or will) receive an event for the raw disk (i.e. "da1")
        # so we ignore this event.
        return

    now = asyncio.get_event_loop().time()
    task = asyncio.get_event_loop().call_later

    if not PREV_TASK:
        if data['cdev'].startswith(DISKS):
            method = added_disk if data['type'] == 'CREATE' else remove_disk
        else:
            method = reset_cache

        PREV_TASK.append({
            'task': task(SETTLE_TIME, lambda: asyncio.ensure_future(method(middleware, data['cdev']))),
            'method': method.__qualname__,
        })
    elif PREV_TASK[-1]['method'] != 'reset_cache':
        # we have a previously scheduled task and the event we received came
        # in within SETTLE_TIME AND the previous task method to be run was
        # not "reset_cache" so we assume that we're receiving a "burst" of
        # events. This happens when a shelf is attached/detached or we have
        # a failure event that causes an undefined pattern of behavior. In
        # either of these scenarios, we need to reset the entirety of the
        # disk cache to play it safe.
        PREV_TASK[-1]['task'].cancel()
        PREV_TASK.append({
            'task': task(SETTLE_TIME, lambda: asyncio.ensure_future(reset_cache(middleware, data['cdev']))),
            'method': 'reset_cache',
        })
    elif 'backoff' not in PREV_TASK[-1]:
        # This means we're continuing to receive a stream of events but we've
        # already created a task to wipe the entirety of the cache so we need
        # to cancel the currently pending task and create a new one to run after
        # MAX_WAIT_TIME to give the system "time to settle down". This shouldn't
        # occur but the logic needs to be here to cover edge-case scenarios.
        PREV_TASK[-1]['task'].cancel()
        PREV_TASK.append({
            'task': task(MAX_WAIT_TIME, lambda: asyncio.ensure_future(reset_cache(middleware, data['cdev']))),
            'method': 'reset_cache',
            'backoff': True,
        })
    elif (PREV_TASK[-1]['task'].when() - now) <= 0:
        # We have continually received a stream of events for at least
        # MAX_WAIT_TIME which means something is misbehaving badly.
        # This is an edge-case so at least log a warning.
        middleware.logger.warning(
            f'Continually received disk events for {MAX_WAIT_TIME} seconds. Disk cache was reset during this time.'
        )


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.register_hook('devd.devfs', devd_devfs_hook)
