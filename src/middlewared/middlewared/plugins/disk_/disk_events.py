from asyncio import ensure_future


async def added_disk(middleware, disk_name):
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)


async def remove_disk(middleware, disk_name):
    await (await middleware.call('disk.sync_all')).wait()
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)
    # If a disk dies we need to reconfigure swaps so we are not left
    # with a single disk mirror swap, which may be a point of failure.
    ensure_future(middleware.call('disk.swaps_configure'))


async def udev_block_devices_hook(middleware, data):
    if data.get('SUBSYSTEM') != 'block' or data.get('DEVTYPE') != 'disk' or data['SYS_NAME'].startswith((
        'dm-', 'loop', 'md', 'sr', 'zd',
    )):
        return

    if data['ACTION'] == 'add':
        await added_disk(middleware, data['SYS_NAME'])
    elif data['ACTION'] == 'remove':
        await remove_disk(middleware, data['SYS_NAME'])


def setup(middleware):
    middleware.register_hook('udev.block', udev_block_devices_hook)
