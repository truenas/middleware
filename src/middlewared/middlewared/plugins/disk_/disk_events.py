from middlewared.utils.disks import DISKS_TO_IGNORE


async def added_disk(middleware, disk_name):
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)
    if await middleware.call('failover.status') == 'MASTER':
        for i in await middleware.call('disk.get_disks', [disk_name]):
            try:
                await middleware.call(
                    'failover.call_remote',
                    'disk.retaste',
                    [[i.serial]],
                    {'raise_connect_error': False}
                )
            except Exception:
                middleware.logger.exception(
                    "Unexpected failure retasting disk on standby"
                )


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


def udev_disk_change_sync_hook(middleware, data):
    if data.get('SUBSYSTEM') != 'block':
        return
    elif data.get('DEVTYPE') != 'disk':
        return
    elif data['SYS_NAME'].startswith(DISKS_TO_IGNORE):
        return
    elif data['ACTION'] == 'change':
        middleware.call_sync('disk.sync_size_if_changed', data['SYS_NAME'])


def setup(middleware):
    middleware.register_hook('udev.block', udev_block_devices_hook)
    middleware.register_hook('udev.block', udev_disk_change_sync_hook)
