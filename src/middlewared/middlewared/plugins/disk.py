from collections import defaultdict
import os
import re
import sys
import sysctl

from bsd import geom
from middlewared.service import filterable, private, CRUDService
from middlewared.utils import run

# FIXME: temporary import of SmartAlert until alert is implemented
# in middlewared
if '/usr/local/www' not in sys.path:
    sys.path.insert(0, '/usr/local/www')
from freenasUI.services.utils import SmartAlert

MIRROR_MAX = 5
RE_ISDISK = re.compile(r'^(da|ada|vtbd|mfid|nvd)[0-9]+$')


class DiskService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        if filters is None:
            filters = []
        if options is None:
            options = {}
        options['prefix'] = 'disk_'
        filters.append(('enabled', '=', True))
        options['extend'] = 'disk.disk_extend'
        return self.middleware.call('datastore.query', 'storage.disk', filters, options)

    @private
    def disk_extend(self, disk):
        disk.pop('enabled', None)
        return disk

    @private
    def swaps_configure(self):
        """
        Configures swap partitions in the system.
        We try to mirror all available swap partitions to avoid a system
        crash in case one of them dies.
        """
        self.middleware.threaded(geom.scan)

        used_partitions = set()
        swap_devices = []
        klass = geom.class_by_name('MIRROR')
        if klass:
            for g in klass.geoms:
                # Skip gmirror that is not swap*
                if not g.name.startswith('swap') or g.name.endswith('.sync'):
                    continue
                swap_devices.append(f'mirror/{g.name}')
                for c in g.consumers:
                    # Add all partitions used in swap, removing .eli
                    used_partitions.add(c.provider.name.strip('.eli'))

        klass = geom.class_by_name('PART')
        if not klass:
            return

        # Get all partitions of swap type, indexed by size
        swap_partitions_by_size = defaultdict(list)
        for g in klass.geoms:
            for p in g.providers:
                if p.name in used_partitions:
                    continue
                # if swap partition
                if p.config['rawtype'] == '516e7cb5-6ecf-11d6-8ff8-00022d09712b':
                    # Try to save a core dump from that
                    run('savecore', '/data/crash/', p.name, check=False)
                    swap_partitions_by_size[p.mediasize].append(p.name)

        unused_partitions = []
        for size, partitions in swap_partitions_by_size.items():
            for i in range(int(len(partitions) / 2)):
                if len(swap_devices) > MIRROR_MAX:
                    break
                part_a, part_b = partitions[0:2]
                partitions = partitions[2:]
                try:
                    name = new_swap_name()
                    run('gmirror', 'create', '-b', 'prefer', name, part_a, part_b)
                except Exception:
                    self.logger.warn(f'Failed to create gmirror {name}', exc_info=True)
                    continue
                swap_devices.append(f'mirror/{name}')
                # Add remaining partitions to unused list
                unused_partitions += partitions

        # If we could not make even a single swap mirror, add the first unused
        # partition as a swap device
        if not swap_devices and unused_partitions:
            swap_devices.append(unused_partitions[0])

        for name in swap_devices:
            # Configure dumpdev on first swap device
            if not os.path.exists('/dev/dumpdev'):
                try:
                    os.unlink('/dev/dumpdev')
                except OSError:
                    pass
                os.symlink(f'/dev/{name}', '/dev/dumpdev')
                run('dumpon', f'/dev/{name}')

            if not os.path.exists(f'/dev/{name}.eli'):
                run('geli', 'onetime', name)
            run('swapon', f'/dev/{name}.eli', check=False)

        return swap_devices

    @private
    def swaps_remove_disks(self, disks):
        """
        Remove a given disk (e.g. ["da0", "da1"]) from swap.
        it will offline if from swap, remove it from the gmirror (if exists)
        and detach the geli.
        """
        self.middleware.threaded(geom.scan)
        providers = {}
        for disk in disks:
            partgeom = geom.geom_by_name('PART', disk)
            if not partgeom:
                continue
            for p in partgeom.providers:
                if p.config['rawtype'] == '516e7cb5-6ecf-11d6-8ff8-00022d09712b':
                    providers[p.id] = p
                    break

        if not providers:
            return

        klass = geom.class_by_name('MIRROR')
        if not klass:
            return

        mirrors = set()
        for g in klass.geoms:
            for c in g.consumers:
                if c.provider.id in providers:
                    mirrors.add(g.name)
                    del providers[c.provider.id]

        for name in mirrors:
            run('swapoff', f'/dev/mirror/{name}.eli')
            if os.path.exists(f'/dev/mirror/{name}.eli'):
                run('geli', 'detach', f'mirror/{name}.eli')
            run('gmirror', 'destroy', name)

        for p in providers.values():
            run('swapoff', f'/dev/{p.name}.eli', check=False)


def new_swap_name():
    """
    Get a new name for a swap mirror

    Returns:
        str: name of the swap mirror
    """
    for i in range(MIRROR_MAX):
        name = f'swap{i}'
        if not os.path.exists(f'/dev/mirror/{name}'):
            return name
    raise RuntimeError('All mirror names are taken')


def _event_devfs(middleware, event_type, args):
    data = args['data']
    if data.get('subsystem') != 'CDEV':
        return

    if data['type'] == 'CREATE':
        disks = middleware.threaded(lambda: sysctl.filter('kern.disks')[0].value.split())
        # Device notified about is not a disk
        if data['cdev'] not in disks:
            return
        # TODO: hack so every disk is not synced independently during boot
        # This is a performance issue
        if os.path.exists('/tmp/.sync_disk_done'):
            middleware.call('notifier.sync_disk', data['cdev'])
            try:
                with SmartAlert() as sa:
                    sa.device_delete(data['cdev'])
            except Exception:
                pass
    elif data['type'] == 'DESTROY':
        # Device notified about is not a disk
        if not RE_ISDISK.match(data['cdev']):
            return
        # TODO: hack so every disk is not synced independently during boot
        # This is a performance issue
        if os.path.exists('/tmp/.sync_disk_done'):
            middleware.call('notifier.sync_disks')
            middleware.call('notifier.multipath_sync')
            try:
                with SmartAlert() as sa:
                    sa.device_delete(data['cdev'])
            except Exception:
                pass


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.event_subscribe('devd.devfs', _event_devfs)
