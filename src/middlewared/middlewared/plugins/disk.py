import asyncio
import errno
import re
import subprocess
from sqlalchemy.exc import IntegrityError

from middlewared.schema import accepts, Bool, Datetime, Dict, Int, Patch, Str
from middlewared.service import filterable, private, CallError, CRUDService
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.asyncio_ import asyncio_map


RE_SED_RDLOCK_EN = re.compile(r'(RLKEna = Y|ReadLockEnabled:\s*1)', re.M)
RE_SED_WRLOCK_EN = re.compile(r'(WLKEna = Y|WriteLockEnabled:\s*1)', re.M)


class DiskModel(sa.Model):
    __tablename__ = 'storage_disk'

    disk_identifier = sa.Column(sa.String(42), primary_key=True)
    disk_name = sa.Column(sa.String(120))
    disk_subsystem = sa.Column(sa.String(10), default='')
    disk_number = sa.Column(sa.Integer(), default=1)
    disk_serial = sa.Column(sa.String(30))
    disk_lunid = sa.Column(sa.String(30), nullable=True)
    disk_size = sa.Column(sa.String(20))
    disk_description = sa.Column(sa.String(120))
    disk_transfermode = sa.Column(sa.String(120), default="Auto")
    disk_hddstandby = sa.Column(sa.String(120), default="Always On")
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
    disk_bus = sa.Column(sa.String(20))


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
        Str('lunid', required=True, null=True),
        Int('size', required=True),
        Str('description', required=True),
        Str('transfermode', required=True),
        Str(
            'hddstandby', required=True, enum=[
                'ALWAYS ON', '5', '10', '20', '30', '60', '120', '180', '240', '300', '330'
            ]
        ),
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
        Str('bus', required=True),
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
            for key in ['togglesmart', 'smartoptions', 'hddstandby', 'critical', 'difference', 'informational']
        ):
            if new['togglesmart']:
                await self.middleware.call('disk.toggle_smart_on', new['name'])
            else:
                await self.middleware.call('disk.toggle_smart_off', new['name'])

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
                'togglesmart', 'advpowermgmt', 'description', 'hddstandby',
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

        devname = f'/dev/{disk_name}'
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

        if locked:
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

        devname = f'/dev/{disk_name}'
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

    @private
    async def configure_power_management(self):
        """
        This runs on boot to properly configure all power management options
        (Advanced Power Management and IDLE) for all disks.
        """
        if await self.middleware.call('system.product_type') != 'SCALE_ENTERPRISE':
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
