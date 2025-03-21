from middlewared.utils.disks import DISKS_TO_IGNORE


async def added_disk(middleware, disk_name):
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)


async def remove_disk(middleware, disk_name):
    await (await middleware.call('disk.sync_all')).wait()


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
