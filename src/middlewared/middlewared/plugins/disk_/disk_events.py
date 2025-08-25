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


async def change_disk(middleware, disk_name):
    await middleware.call('disk.sync_size_if_changed', disk_name)


async def remove_disk(middleware, disk_name):
    await (await middleware.call('disk.sync_all')).wait()


async def should_ignore(data):
    return (
        data.get('SUBSYSTEM') != 'block'
        or data.get('DEVTYPE') != 'disk'
        or data['SYS_NAME'].startswith(DISKS_TO_IGNORE)
    )


async def udev_block_devices_hook(middleware, data):
    if await should_ignore(data):
        return

    if data['ACTION'] == 'add':
        await added_disk(middleware, data['SYS_NAME'])
    elif data['ACTION'] == 'remove':
        await remove_disk(middleware, data['SYS_NAME'])
    elif data['ACTION'] == 'change':
        await change_disk(middleware, data['SYS_NAME'])


def setup(middleware):
    middleware.register_hook('udev.block', udev_block_devices_hook)
