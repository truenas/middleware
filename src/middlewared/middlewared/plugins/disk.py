from sqlalchemy.exc import IntegrityError

from middlewared.utils import ProductType
from middlewared.schema import accepts, Datetime, Dict, Int, Patch, Str
from middlewared.service import filterable, private, CRUDService
import middlewared.sqlalchemy as sa


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
    disk_expiretime = sa.Column(sa.DateTime(), nullable=True)
    disk_enclosure_slot = sa.Column(sa.Integer(), nullable=True)
    disk_passwd = sa.Column(sa.EncryptedText(), default='')
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
        role_prefix = 'DISK'

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
        Str('advpowermgmt', required=True, enum=['DISABLED', '1', '64', '127', '128', '192', '254']),
        Datetime('expiretime', required=True, null=True),
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

        if context['real_names']:
            disk['real_name'] = context['identifier_to_name'].get(disk['identifier'])

        return disk

    @private
    async def disk_extend_context(self, rows, extra):
        context = {
            'passwords': extra.get('passwords', False),
            'disks_keys': {},
            'real_names': extra.get('real_names', False),
            'identifier_to_name': {},

            'pools': extra.get('pools', False),
            'boot_pool_disks': [],
            'boot_pool_name': None,
            'zfs_guid_to_pool': {},
        }

        if context['passwords']:
            context['disks_keys'] = await self.middleware.call('kmip.retrieve_sed_disks_keys')

        if context['real_names']:
            context['identifier_to_name'] = {
                disk.identifier: disk.name
                for disk in await self.middleware.call('disk.get_disks')
            }

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
    async def do_update(self, id_, data):
        """
        Update disk of `id`.
        """

        old = await self.middleware.call(
            'datastore.query', 'storage.disk', [['identifier', '=', id_]], {
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
                self.middleware.create_task(self.middleware.call('kmip.reset_sed_disk_password', id_, new['kmip_uid']))
            new['kmip_uid'] = None

        for key in ['advpowermgmt', 'hddstandby']:
            new[key] = new[key].title()

        self._compress_enclosure(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if any(new[key] != old[key] for key in ['hddstandby', 'advpowermgmt']):
            await self.middleware.call('disk.power_management', new['name'])

        if new['passwd'] and old['passwd'] != new['passwd']:
            await self.middleware.call('kmip.sync_sed_keys', [id_])

        return await self.query([['identifier', '=', id_]], {'get': True})

    @private
    async def copy_settings(self, old, new, copy_settings, copy_description):
        keys = []
        if copy_settings:
            keys += [
                'advpowermgmt', 'hddstandby',
            ]
        if copy_description:
            keys += ['description']

        await self.middleware.call('disk.update', new['identifier'], {k: v for k, v in old.items() if k in keys})

    @private
    async def check_clean(self, disk):
        return not bool(await self.middleware.call('disk.list_partitions', disk))

    @private
    async def configure_power_management(self):
        """
        This runs on boot to properly configure all power management options
        (Advanced Power Management and IDLE) for all disks.
        """
        if await self.middleware.call('system.product_type') != ProductType.ENTERPRISE:
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
    middleware.create_task(middleware.call('disk.configure_power_management'))


def setup(middleware):
    # Run disk tasks once system is ready (e.g. power management)
    middleware.event_subscribe('system.ready', _event_system_ready)
