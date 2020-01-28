import re
import sysctl

RE_ISDISK = re.compile(r'^(da|ada|vtbd|mfid|nvd|pmem)[0-9]+$')


async def devd_devfs_hook(middleware, data):
    if data.get('subsystem') != 'CDEV':
        return

    if data['type'] == 'CREATE':
        disks = await middleware.run_in_thread(lambda: sysctl.filter('kern.disks')[0].value.split())
        # Device notified about is not a disk
        if data['cdev'] not in disks:
            return
        await middleware.call('disk.sync', data['cdev'])
        await middleware.call('disk.sed_unlock', data['cdev'])
        await middleware.call('disk.multipath_sync')
        await middleware.call('alert.oneshot_delete', 'SMART', data['cdev'])
    elif data['type'] == 'DESTROY':
        # Device notified about is not a disk
        if not RE_ISDISK.match(data['cdev']):
            return
        await (await middleware.call('disk.sync_all')).wait()
        await middleware.call('disk.multipath_sync')
        await middleware.call('alert.oneshot_delete', 'SMART', data['cdev'])
        # If a disk dies we need to reconfigure swaps so we are not left
        # with a single disk mirror swap, which may be a point of failure.
        await middleware.call('disk.swaps_configure')


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.register_hook('devd.devfs', devd_devfs_hook)
