from collections import defaultdict
import os
import re
import sys
import sysctl

from bsd import geom
from middlewared.schema import accepts
from middlewared.service import filterable, private, CRUDService
from middlewared.utils import run

# FIXME: temporary import of SmartAlert until alert is implemented
# in middlewared
if '/usr/local/www' not in sys.path:
    sys.path.insert(0, '/usr/local/www')
from freenasUI.services.utils import SmartAlert

MIRROR_MAX = 5
RE_DSKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
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
    def sync(self, name):
        """
        Syncs a disk `name` with the database cache.
        """
        # Skip sync disks on backup node
        if (
            not self.middleware.call('system.is_freenas') and
            self.middleware.call('notifier.failover_licensed') and
            self.middleware.call('notifier.failover_status') == 'BACKUP'
        ):
            return

        # Do not sync geom classes like multipath/hast/etc
        if name.find("/") != -1:
            return

        disks = list(self.middleware.call('device.get_info', 'DISK').keys())

        # Abort if the disk is not recognized as an available disk
        if name not in disks:
            return
        ident = self.middleware.call('notifier.device_to_identifier', name)
        qs = self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', '=', ident)], {'order_by': ['-disk_enabled']})
        if ident and qs:
            disk = qs[0]
        else:
            qs = self.middleware.call('datastore.query', 'storage.disk', [('disk_name', '=', name)])
            for i in qs:
                i['disk_enabled'] = False
                self.middleware.call('datastore.update', 'storage.disk', i['disk_identifier'], i)
            disk = {'disk_identifier': ident}
        disk.update({'disk_name': name, 'disk_enabled': True})

        self.middleware.threaded(geom.scan)
        g = geom.geom_by_name('DISK', name)
        if g:
            if g.provider.config['ident']:
                disk['disk_serial'] = g.provider.config['ident']
            if g.provider.mediasize:
                disk['disk_size'] = g.provider.mediasize
        if not disk.get('disk_serial'):
            disk['disk_serial'] = self.middleware.call('notifier.serial_from_device', name) or ''
        reg = RE_DSKNAME.search(name)
        if reg:
            disk['disk_subsystem'] = reg.group(1)
            disk['disk_number'] = int(reg.group(2))
        if disk.get('disk_identifier'):
            self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
        else:
            disk['disk_identifier'] = self.middleware.call('datastore.insert', 'storage.disk', disk)

        # FIXME: use a truenas middleware plugin
        self.middleware.call('notifier.sync_disk_extra', disk['disk_identifier'], False)

    @private
    @accepts()
    def sync_all(self):
        """
        Synchronyze all disks with the cache in database.
        """
        # Skip sync disks on backup node
        if (
            not self.middleware.call('system.is_freenas') and
            self.middleware.call('notifier.failover_licensed') and
            self.middleware.call('notifier.failover_status') == 'BACKUP'
        ):
            return

        disks = list(self.middleware.call('device.get_info', 'DISK').keys())

        in_disks = {}
        serials = []
        self.middleware.threaded(geom.scan)
        for disk in self.middleware.call('datastore.query', 'storage.disk', [], {'order_by': ['-disk_enabled']}):

            disk_enabled_old = disk['disk_enabled']
            name = self.middleware.call('notifier.identifier_to_device', disk['disk_identifier'])
            if not name or name in in_disks:
                # If we cant translate the indentifier to a device, give up
                # If name has already been seen once then we are probably
                # dealing with with multipath here
                self.middleware.call('datastore.delete', 'storage.disk', disk['disk_identifier'])
                continue
            else:
                disk['disk_enabled'] = True
                disk['disk_name'] = name

            reg = RE_DSKNAME.search(name)
            if reg:
                disk['disk_subsystem'] = reg.group(1)
                disk['disk_number'] = int(reg.group(2))
            serial = ''
            g = geom.geom_by_name('DISK', name)
            if g:
                if g.provider.config['ident']:
                    serial = disk['disk_serial'] = g.provider.config['ident']
                serial += g.provider.config.get('lunid') or ''
                if g.provider.mediasize:
                    disk['disk_size'] = g.provider.mediasize
            if not disk.get('disk_serial'):
                disk['disk_serial'] = self.middleware.call('notifier.serial_from_device', name) or ''
            if not disk['disk_serial']:
                serial = disk['disk_serial'] = self.middleware.call('notifier.serial_from_device', name) or ''

            if serial:
                serials.append(serial)

            if name not in disks:
                disk['disk_enabled'] = False
                if disk_enabled_old:
                    self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                else:
                    # Duplicated disk entries in database
                    self.middleware.call('datastore.delete', 'storage.disk', disk['disk_identifier'])
            else:
                self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)

            # FIXME: use a truenas middleware plugin
            self.middleware.call('notifier.sync_disk_extra', disk['disk_identifier'], False)
            in_disks[name] = disk

        for name in disks:
            if name not in in_disks:
                disk_identifier = self.middleware.call('notifier.device_to_identifier', name)
                qs = self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', '=', disk_identifier)])
                if qs:
                    disk = qs[0]
                else:
                    disk = {'disk_identifier': disk_identifier}
                disk['disk_name'] = name
                serial = ''
                g = geom.geom_by_name('DISK', name)
                if g:
                    if g.provider.config['ident']:
                        serial = disk['disk_serial'] = g.provider.config['ident']
                    serial += g.provider.config.get('lunid') or ''
                    if g.provider.mediasize:
                        disk['disk_size'] = g.provider.mediasize
                if not disk.get('disk_serial'):
                    serial = disk['disk_serial'] = self.middleware.call('notifier.serial_from_device', name) or ''
                if serial:
                    if serial in serials:
                        # Probably dealing with multipath here, do not add another
                        continue
                    else:
                        serials.append(serial)
                reg = RE_DSKNAME.search(name)
                if reg:
                    disk['disk_subsystem'] = reg.group(1)
                    disk['disk_number'] = int(reg.group(2))

                if disk.get('disk_identifier'):
                    self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                else:
                    disk['disk_identifier'] = self.middleware.call('datastore.insert', 'storage.disk', disk)
                # FIXME: use a truenas middleware plugin
                self.middleware.call('notifier.sync_disk_extra', disk['disk_identifier'], True)

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

        dumpdev = False
        unused_partitions = []
        for size, partitions in swap_partitions_by_size.items():
            for i in range(int(len(partitions) / 2)):
                if len(swap_devices) > MIRROR_MAX:
                    break
                part_a, part_b = partitions[0:2]
                partitions = partitions[2:]
                if not dumpdev:
                    dumpdev = dempdev_configure(part_a)
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
            if not dumpdev:
                dumpdev = dempdev_configure(unused_partitions[0])
            swap_devices.append(unused_partitions[0])

        for name in swap_devices:
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
            run('swapoff', f'/dev/mirror/{name}.eli', check=False)
            if os.path.exists(f'/dev/mirror/{name}.eli'):
                run('geli', 'detach', f'mirror/{name}.eli', check=False)
            run('gmirror', 'destroy', name, check=False)

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


def dempdev_configure(name):
    # Configure dumpdev on first swap device
    if not os.path.exists('/dev/dumpdev'):
        try:
            os.unlink('/dev/dumpdev')
        except OSError:
            pass
        os.symlink(f'/dev/{name}', '/dev/dumpdev')
        run('dumpon', f'/dev/{name}')
    return True


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
            middleware.call('disk.sync', data['cdev'])
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
            middleware.call('disk.sync_all')
            middleware.call('notifier.multipath_sync')
            try:
                with SmartAlert() as sa:
                    sa.device_delete(data['cdev'])
            except Exception:
                pass


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.event_subscribe('devd.devfs', _event_devfs)
