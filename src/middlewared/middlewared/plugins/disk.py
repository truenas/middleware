from collections import defaultdict
from datetime import datetime, timedelta
import errno
import os
import re
import subprocess
import sys
import sysctl

from bsd import geom
from middlewared.schema import accepts, Str
from middlewared.service import filterable, private, CallError, CRUDService
from middlewared.utils import Popen, run

# FIXME: temporary import of SmartAlert until alert is implemented
# in middlewared
if '/usr/local/www' not in sys.path:
    sys.path.insert(0, '/usr/local/www')
from freenasUI.services.utils import SmartAlert

DISK_EXPIRECACHE_DAYS = 7
MIRROR_MAX = 5
RE_DA = re.compile('^da[0-9]+$')
RE_DSKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
RE_ISDISK = re.compile(r'^(da|ada|vtbd|mfid|nvd)[0-9]+$')
RE_MPATH_NAME = re.compile(r'[a-z]+(\d+)')


class DiskService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        if filters is None:
            filters = []
        if options is None:
            options = {}
        options['prefix'] = 'disk_'
        filters.append(('expiretime', '=', None))
        options['extend'] = 'disk.disk_extend'
        return await self.middleware.call('datastore.query', 'storage.disk', filters, options)

    @private
    def disk_extend(self, disk):
        disk.pop('enabled', None)
        return disk

    async def __camcontrol_list(self):
        """
        Parse camcontrol devlist -v output to gather
        controller id, channel no and driver from a device

        Returns:
            dict(devname) = dict(drv, controller, channel)
        """

        """
        Hacky workaround

        It is known that at least some HPT controller have a bug in the
        camcontrol devlist output with multiple controllers, all controllers
        will be presented with the same driver with index 0
        e.g. two hpt27xx0 instead of hpt27xx0 and hpt27xx1

        What we do here is increase the controller id by its order of
        appearance in the camcontrol output
        """
        hptctlr = defaultdict(int)

        re_drv_cid = re.compile(r'.* on (?P<drv>.*?)(?P<cid>[0-9]+) bus', re.S | re.M)
        re_tgt = re.compile(r'target (?P<tgt>[0-9]+) .*?lun (?P<lun>[0-9]+) .*\((?P<dv1>[a-z]+[0-9]+),(?P<dv2>[a-z]+[0-9]+)\)', re.S | re.M)
        drv, cid, tgt, lun, dev, devtmp = (None, ) * 6

        camcontrol = {}
        proc = await Popen(['camcontrol', 'devlist', '-v'], stdout=subprocess.PIPE)
        for line in (await proc.communicate())[0].splitlines():
            line = line.decode()
            if not line.startswith('<'):
                reg = re_drv_cid.search(line)
                if not reg:
                    continue
                drv = reg.group('drv')
                if drv.startswith('hpt'):
                    cid = hptctlr[drv]
                    hptctlr[drv] += 1
                else:
                    cid = reg.group('cid')
            else:
                reg = re_tgt.search(line)
                if not reg:
                    continue
                tgt = reg.group('tgt')
                lun = reg.group('lun')
                dev = reg.group('dv1')
                devtmp = reg.group('dv2')
                if dev.startswith('pass'):
                    dev = devtmp
                camcontrol[dev] = {
                    'drv': drv,
                    'controller': int(cid),
                    'channel': int(tgt),
                    'lun': int(lun)
                }
        return camcontrol

    async def __get_twcli(self, controller):

        re_port = re.compile(r'^p(?P<port>\d+).*?\bu(?P<unit>\d+)\b', re.S | re.M)
        proc = await Popen(['/usr/local/sbin/tw_cli', f'/c{controller}', 'show'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = (await proc.communicate())[0].decode()

        units = {}
        for port, unit in re_port.findall(output):
            units[int(unit)] = int(port)
        return units

    async def __get_smartctl_args(self, devname):
        args = [f'/dev/{devname}']
        camcontrol = await self.__camcontrol_list()
        info = camcontrol.get(devname)
        if info is not None:
            if info.get('drv') == 'rr274x_3x':
                channel = info['channel'] + 1
                if channel > 16:
                    channel -= 16
                elif channel > 8:
                    channel -= 8
                args = [
                    '/dev/%s' % info['drv'],
                    '-d',
                    'hpt,%d/%d' % (info['controller'] + 1, channel)
                ]
            elif info.get('drv').startswith('arcmsr'):
                args = [
                    '/dev/%s%d' % (info['drv'], info['controller']),
                    '-d',
                    'areca,%d' % (info['lun'] + 1 + (info['channel'] * 8), )
                ]
            elif info.get('drv').startswith('hpt'):
                args = [
                    '/dev/%s' % info['drv'],
                    '-d',
                    'hpt,%d/%d' % (info['controller'] + 1, info['channel'] + 1)
                ]
            elif info.get('drv') == 'ciss':
                args = [
                    '/dev/%s%d' % (info['drv'], info['controller']),
                    '-d',
                    'cciss,%d' % (info['channel'], )
                ]
            elif info.get('drv') == 'twa':
                twcli = await self.__get_twcli(info['controller'])
                args = [
                    '/dev/%s%d' % (info['drv'], info['controller']),
                    '-d',
                    '3ware,%d' % (twcli.get(info['channel'], -1), )
                ]
        return args

    @private
    async def toggle_smart_off(self, devname):
        args = await self.__get_smartctl_args(devname)
        run('/usr/local/sbin/smartctl', '--smart=off', *args, check=False)

    @private
    async def toggle_smart_on(self, devname):
        args = await self.__get_smartctl_args(devname)
        run('/usr/local/sbin/smartctl', '--smart=on', *args, check=False)

    @private
    async def serial_from_device(self, name):
        args = await self.__get_smartctl_args(name)
        p1 = await Popen(['smartctl', '-i'] + args, stdout=subprocess.PIPE)
        output = (await p1.communicate())[0].decode()
        search = re.search(r'Serial Number:\s+(?P<serial>.+)', output, re.I)
        if search:
            return search.group('serial')
        return None

    @private
    @accepts(Str('name'))
    async def device_to_identifier(self, name):
        """
        Given a device `name` (e.g. da0) returns an unique identifier string
        for this device.
        This identifier is in the form of {type}string, "type" can be one of
        the following:
          - serial_lunid - for disk serial concatenated with the lunid
          - serial - disk serial
          - uuid - uuid of a ZFS GPT partition
          - label - label name from geom label
          - devicename - name of the device if any other could not be used/found

        Returns:
            str - identifier
        """
        await self.middleware.threaded(geom.scan)

        g = geom.geom_by_name('DISK', name)
        if g and g.provider.config.get('ident'):
            serial = g.provider.config['ident']
            lunid = g.provider.config.get('lunid')
            if lunid:
                return f'{{serial_lunid}}{serial}_{lunid}'
            return f'{{serial}}{serial}'

        serial = await self.serial_from_device(name)
        if serial:
            return f'{{serial}}{serial}'

        klass = geom.class_by_name('PART')
        if klass:
            for g in klass.geoms:
                for p in g.providers:
                    if p.name == name:
                        # freebsd-zfs partition
                        if p.config['rawtype'] == '516e7cba-6ecf-11d6-8ff8-00022d09712b':
                            return f'{{uuid}}{p.config["rawuuid"]}'

        g = geom.geom_by_name('LABEL', name)
        if g:
            return f'{{label}}{g.provider.name}'

        g = geom.geom_by_name('DEV', name)
        if g:
            return f'{{devicename}}{name}'

        return ''

    @private
    @accepts(Str('name'))
    async def sync(self, name):
        """
        Syncs a disk `name` with the database cache.
        """
        # Skip sync disks on backup node
        if (
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('notifier.failover_licensed') and
            await self.middleware.call('notifier.failover_status') == 'BACKUP'
        ):
            return

        # Do not sync geom classes like multipath/hast/etc
        if name.find("/") != -1:
            return

        disks = list((await self.middleware.call('device.get_info', 'DISK')).keys())

        # Abort if the disk is not recognized as an available disk
        if name not in disks:
            return
        ident = await self.device_to_identifier(name)
        qs = await self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', '=', ident)], {'order_by': ['disk_expiretime']})
        if ident and qs:
            disk = qs[0]
            new = False
        else:
            new = True
            qs = await self.middleware.call('datastore.query', 'storage.disk', [('disk_name', '=', name)])
            for i in qs:
                i['disk_expiretime'] = datetime.utcnow() + timedelta(days=DISK_EXPIRECACHE_DAYS)
                await self.middleware.call('datastore.update', 'storage.disk', i['disk_identifier'], i)
            disk = {'disk_identifier': ident}
        disk.update({'disk_name': name, 'disk_expiretime': None})

        await self.middleware.threaded(geom.scan)
        g = geom.geom_by_name('DISK', name)
        if g:
            if g.provider.config['ident']:
                disk['disk_serial'] = g.provider.config['ident']
            if g.provider.mediasize:
                disk['disk_size'] = g.provider.mediasize
        if not disk.get('disk_serial'):
            disk['disk_serial'] = await self.serial_from_device(name) or ''
        reg = RE_DSKNAME.search(name)
        if reg:
            disk['disk_subsystem'] = reg.group(1)
            disk['disk_number'] = int(reg.group(2))
        if not new:
            await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
        else:
            disk['disk_identifier'] = await self.middleware.call('datastore.insert', 'storage.disk', disk)

        # FIXME: use a truenas middleware plugin
        await self.middleware.call('notifier.sync_disk_extra', disk['disk_identifier'], False)

    @private
    @accepts()
    async def sync_all(self):
        """
        Synchronyze all disks with the cache in database.
        """
        # Skip sync disks on backup node
        if (
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('notifier.failover_licensed') and
            await self.middleware.call('notifier.failover_status') == 'BACKUP'
        ):
            return

        sys_disks = list((await self.middleware.call('device.get_info', 'DISK')).keys())

        seen_disks = {}
        serials = []
        await self.middleware.threaded(geom.scan)
        for disk in (await self.middleware.call('datastore.query', 'storage.disk', [], {'order_by': ['disk_expiretime']})):

            name = await self.middleware.call('notifier.identifier_to_device', disk['disk_identifier'])
            if not name or name in seen_disks:
                # If we cant translate the indentifier to a device, give up
                # If name has already been seen once then we are probably
                # dealing with with multipath here
                if not disk['disk_expiretime']:
                    disk['disk_expiretime'] = datetime.utcnow() + timedelta(days=DISK_EXPIRECACHE_DAYS)
                    await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                elif disk['disk_expiretime'] < datetime.utcnow():
                    # Disk expire time has surpassed, go ahead and remove it
                    await self.middleware.call('datastore.delete', 'storage.disk', disk['disk_identifier'])
                continue
            else:
                disk['disk_expiretime'] = None
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
                serial = disk['disk_serial'] = await self.serial_from_device(name) or ''

            if serial:
                serials.append(serial)

            # If for some reason disk is not identified as a system disk
            # mark it to expire.
            if name not in sys_disks and not disk['disk_expiretime']:
                    disk['disk_expiretime'] = datetime.utcnow() + timedelta(days=DISK_EXPIRECACHE_DAYS)
            await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)

            # FIXME: use a truenas middleware plugin
            await self.middleware.call('notifier.sync_disk_extra', disk['disk_identifier'], False)
            seen_disks[name] = disk

        for name in sys_disks:
            if name not in seen_disks:
                disk_identifier = await self.device_to_identifier(name)
                qs = await self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', '=', disk_identifier)])
                if qs:
                    new = False
                    disk = qs[0]
                else:
                    new = True
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
                    serial = disk['disk_serial'] = await self.serial_from_device(name) or ''
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

                if not new:
                    await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                else:
                    disk['disk_identifier'] = await self.middleware.call('datastore.insert', 'storage.disk', disk)
                # FIXME: use a truenas middleware plugin
                await self.middleware.call('notifier.sync_disk_extra', disk['disk_identifier'], True)

    async def __multipath_create(self, name, consumers, mode=None):
        """
        Create an Active/Passive GEOM_MULTIPATH provider
        with name ``name`` using ``consumers`` as the consumers for it

        Modes:
            A - Active/Active
            R - Active/Read
            None - Active/Passive

        Returns:
            True in case the label succeeded and False otherwise
        """
        cmd = ["/sbin/gmultipath", "label", name] + consumers
        if mode:
            cmd.insert(2, f'-{mode}')
        p1 = await Popen(cmd, stdout=subprocess.PIPE)
        if (await p1.wait()) != 0:
            return False
        return True

    async def __multipath_next(self):
        """
        Find out the next available name for a multipath named diskX
        where X is a crescenting value starting from 1

        Returns:
            The string of the multipath name to be created
        """
        await self.middleware.threaded(geom.scan)
        numbers = sorted([
            int(RE_MPATH_NAME.search(g.name).group(1))
            for g in geom.class_by_name('MULTIPATH').geoms if RE_MPATH_NAME.match(g.name)
        ])
        if not numbers:
            numbers = [0]
        for number in range(1, numbers[-1] + 2):
            if number not in numbers:
                break
        else:
            raise ValueError('Could not find multipaths')
        return f'disk{number}'

    @private
    @accepts()
    async def multipath_sync(self):
        """
        Synchronize multipath disks

        Every distinct GEOM_DISK that shares an ident (aka disk serial)
        with conjunction of the lunid is considered a multipath and will be
        handled by GEOM_MULTIPATH.

        If the disk is not currently in use by some Volume or iSCSI Disk Extent
        then a gmultipath is automatically created and will be available for use.
        """

        await self.middleware.threaded(geom.scan)

        mp_disks = []
        for g in geom.class_by_name('MULTIPATH').geoms:
            for c in g.consumers:
                p_geom = c.provider.geom
                # For now just DISK is allowed
                if p_geom.clazz.name != 'DISK':
                    self.logger.warn(
                        "A consumer that is not a disk (%s) is part of a "
                        "MULTIPATH, currently unsupported by middleware",
                        p_geom.clazz.name
                    )
                    continue
                mp_disks.append(p_geom.name)

        reserved = []
        async for i in await self.middleware.call('boot.get_disks'):
            reserved.append(i)
        # disks already in use count as reserved as well
        for pool in await self.middleware.call('pool.query'):
            try:
                if pool['is_decrypted']:
                    async for i in await self.middleware.call('pool.get_disks', pool['id']):
                        reserved.append(i)
            except CallError as e:
                # pool could not be available for some reason
                if e.errno != errno.ENOENT:
                    raise

        is_freenas = await self.middleware.call('system.is_freenas')

        serials = defaultdict(list)
        active_active = []
        for g in geom.class_by_name('DISK').geoms:
            if not RE_DA.match(g.name) or g.name in reserved or g.name in mp_disks:
                continue
            if not is_freenas:
                descr = g.provider.config.get('descr') or ''
                if (
                    descr == 'STEC ZeusRAM' or
                    descr.startswith('VIOLIN') or
                    descr.startswith('3PAR')
                ):
                    active_active.append(g.name)
            serial = ''
            v = g.provider.config.get('ident')
            if v:
                serial = v
            v = g.provider.config.get('lunid')
            if v:
                serial += v
            if not serial:
                continue
            size = g.provider.mediasize
            serials[(serial, size)].append(g.name)
            serials[(serial, size)].sort(key=lambda x: int(x[2:]))

        disks_pairs = [disks for disks in list(serials.values())]
        disks_pairs.sort(key=lambda x: int(x[0][2:]))

        # Mode is Active/Passive for FreeNAS
        mode = None if is_freenas else 'R'
        for disks in disks_pairs:
            if not len(disks) > 1:
                continue
            name = await self.__multipath_next()
            await self.__multipath_create(name, disks, 'A' if disks[0] in active_active else mode)

        # Scan again to take new multipaths into account
        await self.middleware.threaded(geom.scan)
        mp_ids = []
        for g in geom.class_by_name('MULTIPATH').geoms:
            _disks = []
            for c in g.consumers:
                p_geom = c.provider.geom
                # For now just DISK is allowed
                if p_geom.clazz.name != 'DISK':
                    continue
                _disks.append(p_geom.name)

            qs = await self.middleware.call('datastore.query', 'storage.disk', [
                ['OR', [
                    ['disk_name', 'in', _disks],
                    ['disk_multipath_member', 'in', _disks],
                ]],
            ])
            if qs:
                diskobj = qs[0]
                mp_ids.append(diskobj['disk_identifier'])
                update = False  # Make sure to not update if nothing changed
                if diskobj['disk_multipath_name'] != g.name:
                    update = True
                    diskobj['disk_multipath_name'] = g.name
                if diskobj['disk_name'] in _disks:
                    _disks.remove(diskobj['disk_name'])
                if _disks and diskobj['disk_multipath_member'] != _disks[-1]:
                    update = True
                    diskobj['disk_multipath_member'] = _disks.pop()
                if update:
                    await self.middleware.call('datastore.update', 'storage.disk', diskobj['disk_identifier'], diskobj)

        # Update all disks which were not identified as MULTIPATH, resetting attributes
        for disk in (await self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', 'nin', mp_ids)])):
            if disk['disk_multipath_name'] or disk['disk_multipath_member']:
                disk['disk_multipath_name'] = ''
                disk['disk_multipath_member'] = ''
                await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)

    @private
    async def swaps_configure(self):
        """
        Configures swap partitions in the system.
        We try to mirror all available swap partitions to avoid a system
        crash in case one of them dies.
        """
        await self.middleware.threaded(geom.scan)

        used_partitions = set()
        swap_devices = []
        klass = geom.class_by_name('MIRROR')
        if klass:
            for g in klass.geoms:
                # Skip gmirror that is not swap*
                if not g.name.startswith('swap') or g.name.endswith('.sync'):
                    continue
                consumers = list(g.consumers)
                # If the mirror is degraded lets remove it and make a new pair
                if len(consumers) == 1:
                    c = consumers[0]
                    await self.swaps_remove_disks([c.provider.geom.name])
                else:
                    swap_devices.append(f'mirror/{g.name}')
                    for c in consumers:
                        # Add all partitions used in swap, removing .eli
                        used_partitions.add(c.provider.name.strip('.eli'))

        klass = geom.class_by_name('PART')
        if not klass:
            return

        # Get all partitions of swap type, indexed by size
        swap_partitions_by_size = defaultdict(list)
        for g in klass.geoms:
            for p in g.providers:
                # if swap partition
                if p.config['rawtype'] == '516e7cb5-6ecf-11d6-8ff8-00022d09712b':
                    # Try to save a core dump from that
                    run('savecore', '/data/crash/', f'/dev/{p.name}', check=False)
                    if p.name not in used_partitions:
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
    async def swaps_remove_disks(self, disks):
        """
        Remove a given disk (e.g. ["da0", "da1"]) from swap.
        it will offline if from swap, remove it from the gmirror (if exists)
        and detach the geli.
        """
        await self.middleware.threaded(geom.scan)
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


async def _event_devfs(middleware, event_type, args):
    data = args['data']
    if data.get('subsystem') != 'CDEV':
        return

    if data['type'] == 'CREATE':
        disks = await middleware.threaded(lambda: sysctl.filter('kern.disks')[0].value.split())
        # Device notified about is not a disk
        if data['cdev'] not in disks:
            return
        # TODO: hack so every disk is not synced independently during boot
        # This is a performance issue
        if os.path.exists('/tmp/.sync_disk_done'):
            await middleware.call('disk.sync', data['cdev'])
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
            await middleware.call('disk.sync_all')
            await middleware.call('disk.multipath_sync')
            try:
                with SmartAlert() as sa:
                    sa.device_delete(data['cdev'])
            except Exception:
                pass


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.event_subscribe('devd.devfs', _event_devfs)
