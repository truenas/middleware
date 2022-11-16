from asyncio import ensure_future

from middlewared.plugins.disk_.enums import DISKS_TO_IGNORE


async def added_disk(middleware, disk_name):
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)
    await middleware.call('disk.remove_degraded_mirrors')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)


async def remove_disk(middleware, disk_name):
    await (await middleware.call('disk.sync_all')).wait()
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)
    # If a disk dies we need to reconfigure swaps so we are not left
    # with a single disk mirror swap, which may be a point of failure.
    ensure_future(middleware.call('disk.swaps_configure'))


async def udev_block_devices_hook(middleware, data):
    if data.get('SUBSYSTEM') != 'block':
        return
    elif data.get('DEVTYPE') != 'disk':
        return
    elif data['SYS_NAME'].startswith(DISKS_TO_IGNORE):
        return

    if data['ACTION'] == 'add':
        await added_disk(middleware, data['SYS_NAME'])
    elif data['ACTION'] == 'remove':
        await remove_disk(middleware, data['SYS_NAME'])


def setup(middleware):
    middleware.register_hook('udev.block', udev_block_devices_hook)
