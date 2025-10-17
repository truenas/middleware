from functools import cache

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetSubsysCreateArgs,
                                     NVMetSubsysCreateResult,
                                     NVMetSubsysDeleteArgs,
                                     NVMetSubsysDeleteResult,
                                     NVMetSubsysEntry,
                                     NVMetSubsysUpdateArgs,
                                     NVMetSubsysUpdateResult)
from middlewared.service import CallError, CRUDService, ValidationErrors, private
from middlewared.utils import secrets
from .mixin import NVMetStandbyMixin

SERIAL_RETRIES = 10
MAX_NQN_LEN = 223
MAX_MODEL_LEN = 40

EXTENDED_CONTEXT_KEY_HOSTS = 'hosts'
EXTENDED_CONTEXT_KEY_NAMESPACES = 'namespaces'
EXTENDED_CONTEXT_KEY_PORTS = 'ports'


class NVMetSubsysModel(sa.Model):
    __tablename__ = 'services_nvmet_subsys'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_subsys_name = sa.Column(sa.String(), nullable=False, unique=True)
    nvmet_subsys_subnqn = sa.Column(sa.String(length=MAX_NQN_LEN), nullable=False, unique=True)
    nvmet_subsys_serial = sa.Column(sa.String(), unique=True)
    nvmet_subsys_allow_any_host = sa.Column(sa.Boolean(), default=False)
    nvmet_subsys_pi_enable = sa.Column(sa.Boolean(), nullable=True, default=None)
    nvmet_subsys_qid_max = sa.Column(sa.Integer(), nullable=True, default=None)
    nvmet_subsys_ieee_oui = sa.Column(sa.Integer(), nullable=True, default=None)
    nvmet_subsys_ana = sa.Column(sa.Boolean(), nullable=True, default=None)


class NVMetSubsysService(CRUDService, NVMetStandbyMixin):

    class Config:
        namespace = 'nvmet.subsys'
        datastore = 'services.nvmet_subsys'
        datastore_prefix = 'nvmet_subsys_'
        datastore_extend_context = "nvmet.subsys.extend_context"
        datastore_extend = "nvmet.subsys.extend"
        cli_private = True
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetSubsysEntry

    @api_method(
        NVMetSubsysCreateArgs,
        NVMetSubsysCreateResult,
        audit='Create NVMe target subsys',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
        """
        Create a NVMe target subsystem (`subsys`).

        When a `subsys` contains one of more `namespaces`, and is associated with one or
        more `ports` then clients may access the storage using NVMe-oF.

        All clients may access the subsystem if the `allow_any_host` attribute is set.  Otherwise,
        access is only permitted to `hosts` who have been associated with the subsystem.

        See `nvmet.host.create` and `nvmet.host_subsys.create`.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_subsys_create')
        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('nvmet.global.reload')
        return await self.get_instance(data['id'])

    @api_method(
        NVMetSubsysUpdateArgs,
        NVMetSubsysUpdateResult,
        audit='Update NVMe target subsys',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update NVMe target subsystem (`subsys`) of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(old['name'])
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_subsys_update', old=old)
        verrors.check()

        async with self._handle_standby_service_state(await self.middleware.call('nvmet.global.running')):
            await self.middleware.call(
                'datastore.update', self._config.datastore, id_, new,
                {'prefix': self._config.datastore_prefix}
            )

        await self.middleware.call('nvmet.global.reload')
        return await self.get_instance(id_)

    @api_method(
        NVMetSubsysDeleteArgs,
        NVMetSubsysDeleteResult,
        audit='Delete NVMe target subsys',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, data):
        """
        Delete NVMe target subsystem (`subsys`) of `id`.
        """
        force = data.get('force', False)
        subsys = await self.get_instance(id_)
        audit_callback(subsys['name'])

        verrors = ValidationErrors()
        namespace_ids = {x['id']: x['nsid'] for x in
                         await self.middleware.call('nvmet.namespace.query', [['subsys.id', '=', id_]])}
        if namespace_ids:
            if force:
                await self.middleware.call('nvmet.namespace.delete_ids', list(namespace_ids))
            else:
                count = len(namespace_ids)
                if count == 1:
                    name = list(namespace_ids.values())[0]
                    verrors.add('nvmet_subsys_delete.id',
                                f'Subsystem {subsys["name"]} contains 1 namespace: {name}')
                else:
                    names = list(namespace_ids.values())
                    names.sort()
                    names = [str(name) for name in names[:3]]
                    postfix = ",..." if count > 3 else ""
                    verrors.add('nvmet_subsys_delete.id',
                                f'Subsystem {subsys["name"]} contains {count} namespaces: {",".join(names)}{postfix}')

        port_subsys_ids = [x['id'] for x in await self.middleware.call('nvmet.port_subsys.query',
                                                                       [['subsys.id', '=', id_]],
                                                                       {'select': ['id']})]
        if port_subsys_ids:
            if force:
                await self.middleware.call('nvmet.port_subsys.delete_ids', list(port_subsys_ids))
            else:
                count = len(port_subsys_ids)
                verrors.add('nvmet_subsys_delete.id',
                            f'Subsystem {subsys["name"]} visible on {count} {"ports" if count > 1 else "port"}')

        verrors.check()

        # We will allow a subsys to be deleted, even if it currently has allowed_hosts configured
        host_subsys_ids = [x['id'] for x in await self.middleware.call('nvmet.host_subsys.query',
                                                                       [['subsys.id', '=', id_]],
                                                                       {'select': ['id']})]
        if host_subsys_ids:
            await self.middleware.call('nvmet.host_subsys.delete_ids', host_subsys_ids)

        async with self._handle_standby_service_state(await self.middleware.call('nvmet.global.running')):
            rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await self.middleware.call('nvmet.global.reload')
        return rv

    @private
    async def extend_context(self, rows, extra):
        if extra.get('verbose'):
            return {
                EXTENDED_CONTEXT_KEY_HOSTS: await self.middleware.call('nvmet.host_subsys.query'),
                EXTENDED_CONTEXT_KEY_NAMESPACES: await self.middleware.call('nvmet.namespace.query'),
                EXTENDED_CONTEXT_KEY_PORTS: await self.middleware.call('nvmet.port_subsys.query'),
            }
        return {}

    @private
    async def extend(self, data, context):
        if context:
            subsys_id = data['id']
            data['hosts'] = [item['host']['id'] for item in
                             context[EXTENDED_CONTEXT_KEY_HOSTS] if item['subsys']['id'] == subsys_id]
            data['ports'] = [item['port']['id'] for item in
                             context[EXTENDED_CONTEXT_KEY_PORTS] if item['subsys']['id'] == subsys_id]
            data['namespaces'] = [item['id'] for item in
                                  context[EXTENDED_CONTEXT_KEY_NAMESPACES] if item['subsys']['id'] == subsys_id]

        return data

    @private
    async def subsys_serial(self, serial):
        if serial not in (None, ''):
            return serial
        used_serials = [i['serial'] for i in (
            await self.middleware.call('nvmet.subsys.query', [], {'select': ['serial']})
        )]
        for i in range(SERIAL_RETRIES):
            serial = secrets.token_hex()[:20]
            if serial not in used_serials:
                return serial
        raise CallError('Failed to generate a random serial for subsystem')

    @private
    async def subsys_subnqn(self, subnqn, name):
        if subnqn not in (None, ''):
            return subnqn

        basenqn = (await self.middleware.call('nvmet.global.config'))['basenqn']
        return f'{basenqn}:{name}'[:MAX_NQN_LEN]

    async def __validate(self, verrors, data, schema_name, old=None):
        id_ = old['id'] if old else None
        await self._ensure_unique(verrors, schema_name, 'name', data['name'], id_)
        data['serial'] = await self.subsys_serial(data.get('serial'))
        data['subnqn'] = await self.subsys_subnqn(data.get('subnqn'), data.get('name', ''))
        if data['ana'] is not None:
            if not await self.middleware.call('failover.licensed'):
                verrors.add(
                    f'{schema_name}.ana',
                    'This platform does not support Asymmetric Namespace Access(ANA).'
                )

    @private
    @cache
    def model(self):
        vendor = self.middleware.call_sync('system.vendor.name')
        dmiinfo = self.middleware.call_sync('system.dmidecode_info')
        if dmiinfo.get('system-manufacturer') == 'QEMU':
            system_product = 'KVM VM'
        else:
            system_product = dmiinfo.get('system-product-name', '')

        if vendor:
            return (system_product or vendor)[:MAX_MODEL_LEN]
        else:
            if system_product.lower().startswith('truenas'):
                return system_product[:MAX_MODEL_LEN]
            return f'TrueNAS {system_product}'[:MAX_MODEL_LEN]

    @private
    @cache
    def firmware(self):
        if version := self.middleware.call_sync('system.version_short'):
            return version[:8]
        return 'Unknown'
