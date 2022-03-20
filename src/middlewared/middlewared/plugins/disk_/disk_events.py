import asyncio

DISK = ('da', 'ada', 'vtbd', 'mfid', 'nvd', 'pmem')
SHELF = ('ses',)
PREVIOUS = {'method': '', 'task': None}
MAX_WAIT_TIME = 60
SETTLE_TIME = 2
LAST_EVENT_TIME = None


async def reset_cache(middleware, *args):
    await middleware.call('geom.cache.invalidate')
    await (await middleware.call('disk.sync_all')).wait()
    await middleware.call('sed_unlock_all')


async def added_disk(middleware, disk_name):
    await middleware.call('geom.cache.invalidate')
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)
    await middleware.call('disk.multipath_sync')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)


async def remove_disk(middleware, disk_name):
    await middleware.call('geom.cache.remove_disk', disk_name)
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.multipath_sync')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)
    # If a disk dies we need to reconfigure swaps so we are not left
    # with a single disk mirror swap, which may be a point of failure.
    asyncio.ensure_future(middleware.call('disk.swaps_configure'))


async def devd_devfs_hook(middleware, data):
    if data.get('subsystem') != 'CDEV' or data['type'] not in ('CREATE', 'DESTROY'):
        return
    elif not data['cdev'].startswith(DISK + SHELF):
        return

    now = asyncio.get_event_loop().time()

    global PREVIOUS, LAST_EVENT_TIME
    if not PREVIOUS['task']:
        if data['cdev'].startswith(DISK):
            method = added_disk if data['type'] == 'CREATE' else remove_disk
        else:
            method = reset_cache

            PREVIOUS['task'] = asyncio.get_event_loop().call_later(
                SETTLE_TIME, lambda: asyncio.ensure_future(method(middleware, data['cdev']))
            )
            PREVIOUS['method'] = method.__name__
            LAST_EVENT_TIME = now
    elif PREVIOUS['method'] != 'reset_cache':
        # we have a previously scheduled task and the event we received came
        # in within SETTLE_TIME AND the previous task method to be run was
        # not "reset_cache" so we assume that we're receiving a "burst" of
        # events. This happens when a shelf is attached/detached or we have
        # a failure event that causes an undefined pattern of behavior. In
        # either of these scenarios, we need to reset the entirety of the
        # disk cache to play it safe.
        PREVIOUS['task'].cancel()
        PREVIOUS['task'] = asyncio.get_event_loop().call_later(
            SETTLE_TIME, lambda: asyncio.ensure_future(reset_cache(middleware))
        )
        PREVIOUS['method'] = 'reset_cache'
    elif (now - LAST_EVENT_TIME >= MAX_WAIT_TIME):
        # we have continually received a stream of events for at least
        # MAX_WAIT_TIME which means something is misbehaving badly. Log
        # a warning and run the method directly
        PREVIOUS['task'].cancel()
        PREVIOUS = {'method': '', 'task': None}
        LAST_EVENT_TIME = None

        err = f'Waited at least {MAX_WAIT_TIME}seconds but have continually received devd events.'
        err += ' Resetting disk cache.'
        middleware.logger.warning(err)
        await reset_cache(middleware)


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.register_hook('devd.devfs', devd_devfs_hook)
