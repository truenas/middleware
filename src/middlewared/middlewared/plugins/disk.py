import asyncio
from collections import defaultdict
import errno
import re
import subprocess

from sqlalchemy.exc import IntegrityError

try:
    from bsd import geom
    from nvme import get_nsid
except ImportError:
    geom = None
    get_nsid = None

from middlewared.common.camcontrol import camcontrol_list
from middlewared.schema import accepts, Bool, Datetime, Dict, Int, List, Patch, Ref, returns, Str
from middlewared.service import filterable, private, CallError, CRUDService
from middlewared.service_exception import ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import osc, run
from middlewared.utils.asyncio_ import asyncio_map


RE_DA = re.compile('^da[0-9]+$')
RE_MPATH_NAME = re.compile(r'[a-z]+(\d+)')
RE_SED_RDLOCK_EN = re.compile(r'(RLKEna = Y|ReadLockEnabled:\s*1)', re.M)
RE_SED_WRLOCK_EN = re.compile(r'(WLKEna = Y|WriteLockEnabled:\s*1)', re.M)


class DiskModel(sa.Model):
    __tablename__ = 'storage_disk'

    disk_identifier = sa.Column(sa.String(42), primary_key=True)
    disk_name = sa.Column(sa.String(120))
    disk_subsystem = sa.Column(sa.String(10), default='')
    disk_number = sa.Column(sa.Integer(), default=1)
    disk_serial = sa.Column(sa.String(30))
    disk_size = sa.Column(sa.String(20))
    disk_multipath_name = sa.Column(sa.String(30))
    disk_multipath_member = sa.Column(sa.String(30))
    disk_description = sa.Column(sa.String(120))
    disk_transfermode = sa.Column(sa.String(120), default="Auto")
    disk_hddstandby = sa.Column(sa.String(120), default="Always On")
    disk_hddstandby_force = sa.Column(sa.Boolean(), default=False)
    disk_advpowermgmt = sa.Column(sa.String(120), default="Disabled")
    disk_togglesmart = sa.Column(sa.Boolean(), default=True)
    disk_smartoptions = sa.Column(sa.String(120))
    disk_expiretime = sa.Column(sa.DateTime(), nullable=True)
    disk_enclosure_slot = sa.Column(sa.Integer(), nullable=True)
    disk_passwd = sa.Column(sa.EncryptedText(), default='')
    disk_critical = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_difference = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_informational = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_model = sa.Column(sa.String(200), nullable=True, default=None)
    disk_rotationrate = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_type = sa.Column(sa.String(20), default='UNKNOWN')
    disk_kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)
    disk_zfs_guid = sa.Column(sa.String(20), nullable=True)


class DiskService(CRUDService):

    class Config:
        datastore = 'storage.disk'
        datastore_prefix = 'disk_'
        datastore_extend = 'disk.disk_extend'
        datastore_extend_context = 'disk.disk_extend_context'
        datastore_primary_key = 'identifier'
        datastore_primary_key_type = 'string'
        event_register = False
        event_send = False
        cli_namespace = 'storage.disk'

    ENTRY = Dict(
        'disk_entry',
        Str('identifier', required=True),
        Str('name', required=True),
        Str('subsystem', required=True),
        Int('number', required=True),
        Str('serial', required=True),
        Int('size', required=True),
        Str('multipath_name', required=True),
        Str('multipath_member', required=True),
        Str('description', required=True),
        Str('transfermode', required=True),
        Str(
            'hddstandby', required=True, enum=[
                'ALWAYS ON', '5', '10', '20', '30', '60', '120', '180', '240', '300', '330'
            ]
        ),
        Bool('hddstandby_force', required=True),
        Bool('togglesmart', required=True),
        Str('advpowermgmt', required=True, enum=['DISABLED', '1', '64', '127', '128', '192', '254']),
        Str('smartoptions', required=True),
        Datetime('expiretime', required=True, null=True),
        Int('critical', required=True, null=True),
        Int('difference', required=True, null=True),
        Int('informational', required=True, null=True),
        Str('model', required=True, null=True),
        Int('rotationrate', required=True, null=True),
        Str('type', required=True, null=True),
        Str('zfs_guid', required=True, null=True),
        Str('devname', required=True),
        Dict(
            'enclosure',
            Int('number'),
            Int('slot'),
            null=True, required=True
        ),
        Str('pool', null=True, required=True),
        Str('passwd', private=True),
        Str('kmip_uid', null=True),
    )

    @filterable
    async def query(self, filters, options):
        """
        Query disks.

        The following extra options are supported:

             include_expired: true - will also include expired disks (default: false)
             passwords: true - will not hide KMIP password for the disks (default: false)
             pools: true - will join pool name for each disk (default: false)
        """
        filters = filters or []
        options = options or {}
        if not options.get('extra', {}).get('include_expired', False):
            filters += [('expiretime', '=', None)]

        return await super().query(filters, options)

    @private
    async def disk_extend(self, disk, context):
        disk.pop('enabled', None)
        for key in ['advpowermgmt', 'hddstandby']:
            disk[key] = disk[key].upper()
        try:
            disk['size'] = int(disk['size'])
        except ValueError:
            disk['size'] = None
        if disk['multipath_name']:
            disk['devname'] = f'multipath/{disk["multipath_name"]}'
        else:
            disk['devname'] = disk['name']
        self._expand_enclosure(disk)
        if context['passwords']:
            if not disk['passwd']:
                disk['passwd'] = context['disks_keys'].get(disk['identifier'], '')
        else:
            disk.pop('passwd')
            disk.pop('kmip_uid')
        if disk['name'] in context['boot_pool_disks']:
            disk['pool'] = context['boot_pool_name']
        else:
            disk['pool'] = context['zfs_guid_to_pool'].get(disk['zfs_guid'])
        return disk

    @private
    async def disk_extend_context(self, rows, extra):
        context = {
            'passwords': extra.get('passwords', False),
            'disks_keys': {},

            'pools': extra.get('pools', False),
            'boot_pool_disks': [],
            'boot_pool_name': None,
            'zfs_guid_to_pool': {},
        }

        if context['passwords']:
            context['disks_keys'] = await self.middleware.call('kmip.retrieve_sed_disks_keys')

        if context['pools']:
            context['boot_pool_disks'] = await self.middleware.call('boot.get_disks')
            context['boot_pool_name'] = await self.middleware.call('boot.pool_name')

            for pool in await self.middleware.call('zfs.pool.query'):
                topology = await self.middleware.call('pool.transform_topology_lightweight', pool['groups'])
                for vdev in await self.middleware.call('pool.flatten_topology', topology):
                    if vdev['type'] == 'DISK':
                        context['zfs_guid_to_pool'][vdev['guid']] = pool['name']

        return context

    def _expand_enclosure(self, disk):
        if disk['enclosure_slot'] is not None:
            disk['enclosure'] = {
                'number': disk['enclosure_slot'] // 1000,
                'slot': disk['enclosure_slot'] % 1000
            }
        else:
            disk['enclosure'] = None
        del disk['enclosure_slot']

    def _compress_enclosure(self, disk):
        if disk['enclosure'] is not None:
            disk['enclosure_slot'] = disk['enclosure']['number'] * 1000 + disk['enclosure']['slot']
        else:
            disk['enclosure_slot'] = None
        del disk['enclosure']

    @accepts(
        Str('id'),
        Patch(
            'disk_entry', 'disk_update',
            ('rm', {'name': 'identifier'}),
            ('rm', {'name': 'name'}),
            ('rm', {'name': 'subsystem'}),
            ('rm', {'name': 'serial'}),
            ('rm', {'name': 'kmip_uid'}),
            ('rm', {'name': 'size'}),
            ('rm', {'name': 'multipath_name'}),
            ('rm', {'name': 'multipath_member'}),
            ('rm', {'name': 'transfermode'}),
            ('rm', {'name': 'expiretime'}),
            ('rm', {'name': 'model'}),
            ('rm', {'name': 'rotationrate'}),
            ('rm', {'name': 'type'}),
            ('rm', {'name': 'zfs_guid'}),
            ('rm', {'name': 'devname'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, id, data):
        """
        Update disk of `id`.

        If extra options need to be passed to SMART which we don't already support, they can be passed by
        `smartoptions`.

        `critical`, `informational` and `difference` are integer values on which alerts for SMART are configured
        if the disk temperature crosses the assigned threshold for each respective attribute.
        If they are set to null, then SMARTD config values are used as defaults.

        Email of log level LOG_CRIT is issued when disk temperature crosses `critical`.

        Email of log level LOG_INFO is issued when disk temperature crosses `informational`.

        If temperature of a disk changes by `difference` degree Celsius since the last report, SMART reports this.
        """

        old = await self.middleware.call(
            'datastore.query', 'storage.disk', [['identifier', '=', id]], {
                'get': True, 'prefix': self._config.datastore_prefix
            }
        )
        old.pop('enabled', None)
        self._expand_enclosure(old)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new['hddstandby_force']:
            if new['hddstandby'] == 'ALWAYS ON':
                verrors.add(
                    'disk_update.hddstandby_force',
                    'This option does not have sense when HDD Standby is not set'
                )

        if verrors:
            raise verrors

        if not new['passwd'] and old['passwd'] != new['passwd']:
            # We want to make sure kmip uid is None in this case
            if new['kmip_uid']:
                asyncio.ensure_future(self.middleware.call('kmip.reset_sed_disk_password', id, new['kmip_uid']))
            new['kmip_uid'] = None

        for key in ['advpowermgmt', 'hddstandby']:
            new[key] = new[key].title()

        self._compress_enclosure(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if any(new[key] != old[key] for key in ['hddstandby', 'advpowermgmt']):
            await self.middleware.call('disk.power_management', new['name'])

        if any(
            new[key] != old[key]
            for key in [
                'togglesmart', 'smartoptions', 'hddstandby', 'hddstandby_force',
                'critical', 'difference', 'informational',
            ]
        ):
            if new['togglesmart']:
                await self.middleware.call('disk.toggle_smart_on', new['name'])
            else:
                await self.middleware.call('disk.toggle_smart_off', new['name'])

            await self.middleware.call('disk.update_hddstandby_force')
            await self.middleware.call('disk.update_smartctl_args_for_disks')
            await self.middleware.call('service.restart', 'collectd')
            await self._service_change('smartd', 'restart')
            await self._service_change('snmp', 'restart')

        if new['passwd'] and old['passwd'] != new['passwd']:
            await self.middleware.call('kmip.sync_sed_keys', [id])

        return await self.query([['identifier', '=', id]], {'get': True})

    @private
    async def copy_settings(self, old, new):
        await self.middleware.call('disk.update', new['identifier'], {
            k: v for k, v in old.items() if k in [
                'togglesmart', 'advpowermgmt', 'description', 'hddstandby', 'hddstandby_force',
                'smartoptions', 'critical', 'difference', 'informational',
            ]
        })

        changed = False
        for row in await self.middleware.call('datastore.query', 'tasks.smarttest_smarttest_disks', [
            ['disk_id', '=', old['identifier']],
        ], {'relationships': False}):
            try:
                await self.middleware.call('datastore.insert', 'tasks.smarttest_smarttest_disks', {
                    'smarttest_id': row['smarttest_id'],
                    'disk_id': new['identifier'],
                })
            except IntegrityError:
                pass
            else:
                changed = True

        if changed:
            asyncio.ensure_future(self._service_change('smartd', 'restart'))

    @private
    def get_name(self, disk):
        if disk["multipath_name"]:
            return f"multipath/{disk['multipath_name']}"
        else:
            return disk["name"]

    @accepts(Bool("join_partitions", default=False))
    @returns(List('unused_disks', items=[Ref('disk_entry')]))
    async def get_unused(self, join_partitions):
        """
        Helper method to get all disks that are not in use, either by the boot
        pool or the user pools.
        """
        disks = await self.query([('devname', 'nin', await self.get_reserved())])

        if join_partitions:
            for disk in disks:
                disk['partitions'] = await self.middleware.call('disk.list_partitions', disk['devname'])

        return disks

    @private
    async def get_reserved(self):
        reserved = list(await self.middleware.call('boot.get_disks'))
        reserved += await self.middleware.call('pool.get_disks')
        if osc.IS_FREEBSD:
            # FIXME: Make this freebsd specific for now
            reserved += [i async for i in self.__get_iscsi_targets()]
        return reserved

    async def __get_iscsi_targets(self):
        iscsi_target_extent_paths = [
            extent["iscsi_target_extent_path"]
            for extent in await self.middleware.call('datastore.query', 'services.iscsitargetextent',
                                                     [('iscsi_target_extent_type', '=', 'Disk')])
        ]
        for disk in await self.middleware.call('datastore.query', 'storage.disk',
                                               [('disk_identifier', 'in', iscsi_target_extent_paths)]):
            yield disk["disk_name"]

    @private
    async def check_clean(self, disk):
        return not bool(await self.middleware.call('disk.list_partitions', disk))

    @private
    async def sed_unlock_all(self):
        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        advconfig = await self.middleware.call('system.advanced.config')
        disks = await self.middleware.call('disk.query', [], {'extra': {'passwords': True}})

        # If no SED password was found we can stop here
        if not await self.middleware.call('system.advanced.sed_global_password') and not any(
            [d['passwd'] for d in disks]
        ):
            return

        result = await asyncio_map(lambda disk: self.sed_unlock(disk['name'], disk, advconfig), disks, 16)
        locked = list(filter(lambda x: x['locked'] is True, result))
        if locked:
            disk_names = ', '.join([i['name'] for i in locked])
            self.logger.warn(f'Failed to unlock following SED disks: {disk_names}')
            raise CallError('Failed to unlock SED disks', errno.EACCES)
        return True

    @private
    async def sed_unlock(self, disk_name, disk=None, _advconfig=None):
        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        if _advconfig is None:
            _advconfig = await self.middleware.call('system.advanced.config')

        devname = await self.middleware.call('disk.sed_dev_name', disk_name)
        # We need two states to tell apart when disk was successfully unlocked
        locked = None
        unlocked = None
        password = await self.middleware.call('system.advanced.sed_global_password')

        if disk is None:
            disk = await self.query([('name', '=', disk_name)], {'extra': {'passwords': True}})
            if disk and disk[0]['passwd']:
                password = disk[0]['passwd']
        elif disk.get('passwd'):
            password = disk['passwd']

        rv = {'name': disk_name, 'locked': None}

        if not password:
            # If there is no password no point in continuing
            return rv

        # Try unlocking TCG OPAL using sedutil
        cp = await run('sedutil-cli', '--query', devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode(errors='ignore')
            if 'Locked = Y' in output:
                locked = True
                cp = await run('sedutil-cli', '--setLockingRange', '0', 'RW', password, devname, check=False)
                if cp.returncode == 0:
                    locked = False
                    unlocked = True
                    # If we were able to unlock it, let's set mbrenable to off
                    if osc.IS_LINUX:
                        cp = await run('sedutil-cli', '--setMBREnable', 'off', password, devname, check=False)
                        if cp.returncode:
                            self.logger.error(
                                'Failed to set MBREnable for %r to "off": %s', devname,
                                cp.stderr.decode(), exc_info=True
                            )

            elif 'Locked = N' in output:
                locked = False

        # Try ATA Security if SED was not unlocked and its not locked by OPAL
        if not unlocked and not locked:
            locked, unlocked = await self.middleware.call('disk.unlock_ata_security', devname, _advconfig, password)

        if osc.IS_FREEBSD and unlocked:
            try:
                # Disk needs to be retasted after unlock
                with open(f'/dev/{disk_name}', 'wb'):
                    pass
            except OSError:
                pass
        elif locked:
            self.logger.error(f'Failed to unlock {disk_name}')
        rv['locked'] = locked
        return rv

    @private
    async def sed_initial_setup(self, disk_name, password):
        """
        NO_SED - Does not support SED
        ACCESS_GRANTED - Already setup and `password` is a valid password
        LOCKING_DISABLED - Locking range is disabled
        SETUP_FAILED - Initial setup call failed
        SUCCESS - Setup successfully completed
        """
        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        devname = await self.middleware.call('disk.sed_dev_name', disk_name)

        cp = await run('sedutil-cli', '--isValidSED', devname, check=False)
        if b' SED ' not in cp.stdout:
            return 'NO_SED'

        cp = await run('sedutil-cli', '--listLockingRange', '0', password, devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode()
            if RE_SED_RDLOCK_EN.search(output) and RE_SED_WRLOCK_EN.search(output):
                return 'ACCESS_GRANTED'
            else:
                return 'LOCKING_DISABLED'

        try:
            await run('sedutil-cli', '--initialSetup', password, devname)
        except subprocess.CalledProcessError as e:
            self.logger.debug(f'initialSetup failed for {disk_name}:\n{e.stdout}{e.stderr}')
            return 'SETUP_FAILED'

        # OPAL 2.0 disks do not enable locking range on setup like Enterprise does
        try:
            await run('sedutil-cli', '--enableLockingRange', '0', password, devname)
        except subprocess.CalledProcessError as e:
            self.logger.debug(f'enableLockingRange failed for {disk_name}:\n{e.stdout}{e.stderr}')
            return 'SETUP_FAILED'

        return 'SUCCESS'

    def sed_dev_name(self, disk_name):
        if disk_name.startswith("nvd"):
            nvme = get_nsid(f"/dev/{disk_name}")
            return f"/dev/{nvme}"

        return f"/dev/{disk_name}"

    @private
    async def multipath_create(self, name, consumers, mode=None):
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
        try:
            await run(cmd, stderr=subprocess.STDOUT, encoding="utf-8", errors="ignore")
        except subprocess.CalledProcessError as e:
            raise CallError(f"Error creating multipath: {e.stdout}")

    async def __multipath_next(self):
        """
        Find out the next available name for a multipath named diskX
        where X is a crescenting value starting from 1

        Returns:
            The string of the multipath name to be created
        """
        await self.middleware.run_in_thread(geom.scan)
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

        await self.middleware.run_in_thread(geom.scan)

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

        reserved = await self.get_reserved()

        devlist = await camcontrol_list()
        is_enterprise = await self.middleware.call('system.is_enterprise')

        serials = defaultdict(list)
        active_active = []
        for g in geom.class_by_name('DISK').geoms:
            if not RE_DA.match(g.name) or g.name in reserved or g.name in mp_disks:
                continue
            if is_enterprise:
                descr = g.provider.config.get('descr') or ''
                if (
                    descr == 'STEC ZeusRAM' or
                    descr.startswith('VIOLIN') or
                    descr.startswith('3PAR')
                ):
                    active_active.append(g.name)
            if devlist.get(g.name, {}).get('driver') == 'umass-sim':
                continue
            serial = ''
            v = g.provider.config.get('ident')
            if v:
                # Exclude fake serial numbers e.g. `000000000000` reported by FreeBSD 12.2 USB stack
                if not v.replace('0', ''):
                    continue
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

        # Mode is Active/Passive for TrueNAS HA
        mode = None if not is_enterprise else 'R'
        for disks in disks_pairs:
            if not len(disks) > 1:
                continue
            name = await self.__multipath_next()
            try:
                await self.multipath_create(name, disks, 'A' if disks[0] in active_active else mode)
            except CallError as e:
                self.logger.error("Error creating multipath: %s", e.errmsg)

        # Scan again to take new multipaths into account
        await self.middleware.run_in_thread(geom.scan)
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
                ['disk_expiretime', '=', None],
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
        disks = await self.middleware.call(
            'datastore.query', 'storage.disk', [('disk_identifier', 'nin', mp_ids)]
        )
        for disk in disks:
            if disk['disk_multipath_name'] or disk['disk_multipath_member']:
                disk['disk_multipath_name'] = ''
                disk['disk_multipath_member'] = ''
                await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)

    @private
    async def check_disks_availability(self, verrors, disks, schema):
        """
        Makes sure the disks are present in the system and not reserved
        by anything else (boot, pool, iscsi, etc).

        Returns:
            dict - disk.query for all disks
        """
        disks_cache = dict(map(
            lambda x: (x['devname'], x),
            await self.middleware.call(
                'disk.query', [('devname', 'in', disks)]
            )
        ))

        disks_set = set(disks)
        disks_not_in_cache = disks_set - set(disks_cache.keys())
        if disks_not_in_cache:
            verrors.add(
                f'{schema}.topology',
                f'The following disks were not found in system: {"," .join(disks_not_in_cache)}.'
            )

        disks_reserved = await self.middleware.call('disk.get_reserved')
        disks_reserved = disks_set - (disks_set - set(disks_reserved))
        if disks_reserved:
            verrors.add(
                f'{schema}.topology',
                f'The following disks are already in use: {"," .join(disks_reserved)}.'
            )
        return disks_cache

    @private
    async def configure_power_management(self):
        """
        This runs on boot to properly configure all power management options
        (Advanced Power Management and IDLE) for all disks.
        """
        # Do not run power management on ENTERPRISE
        if await self.middleware.call('system.product_type') == 'ENTERPRISE':
            return
        for disk in await self.middleware.call('disk.query'):
            await self.middleware.call('disk.power_management', disk['name'], disk)

    @private
    async def power_management(self, dev, disk=None):
        """
        Actually sets power management for `dev`.
        `disk` is the disk.query entry and optional so this can be called only with disk name.
        """

        if not disk:
            disk = await self.middleware.call('disk.query', [('name', '=', dev)])
            if not disk:
                return
            disk = disk[0]

        return await self.middleware.call('disk.power_management_impl', dev, disk)


async def _event_system_ready(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    # Configure disks power management
    asyncio.ensure_future(middleware.call('disk.configure_power_management'))


def setup(middleware):
    # Run disk tasks once system is ready (e.g. power management)
    middleware.event_subscribe('system', _event_system_ready)
