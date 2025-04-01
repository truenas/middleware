import base64

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetHostCreateArgs, NVMetHostCreateResult, NVMetHostDeleteArgs,
                                     NVMetHostDeleteResult, NVMetHostEntry, NVMetHostUpdateArgs, NVMetHostUpdateResult)
from middlewared.service import CRUDService, ValidationErrors, private
from .constants import DHCHAP_DHGROUP, DHCHAP_HASH


class NVMetHostModel(sa.Model):
    __tablename__ = 'services_nvmet_host'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_host_hostnqn = sa.Column(sa.String(255), unique=True)
    nvmet_host_dhchap_key = sa.Column(sa.EncryptedText(), nullable=True)
    nvmet_host_dhchap_ctrl_key = sa.Column(sa.EncryptedText(), nullable=True)
    nvmet_host_dhchap_dhgroup = sa.Column(sa.Integer(), default=0)
    nvmet_host_dhchap_hash = sa.Column(sa.Integer(), default=0)


class NVMetHostService(CRUDService):

    class Config:
        namespace = 'nvmet.host'
        datastore = 'services.nvmet_host'
        datastore_prefix = 'nvmet_host_'
        datastore_extend = 'nvmet.host.extend'
        cli_namespace = 'sharing.nvmet.host'
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetHostEntry

    @api_method(
        NVMetHostCreateArgs,
        NVMetHostCreateResult,
        audit='Create NVMe target host',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_host_create')
        verrors.check()

        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(data['id'])

    @api_method(
        NVMetHostUpdateArgs,
        NVMetHostUpdateResult,
        audit='Update NVMe target host',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update NVMe target host of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(old['hostnqn'])
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_host_update', old=old)
        verrors.check()

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(id_)

    @api_method(
        NVMetHostDeleteArgs,
        NVMetHostDeleteResult,
        audit='Delete NVMe target host',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, options):
        force = options.get('force', False)
        verrors = ValidationErrors()
        host = await self.get_instance(id_)
        audit_callback(host['hostnqn'])

        host_subsys_ids = {x['id']: x['subsys']['nvmet_subsys_name'] for x in
                           await self.middleware.call('nvmet.host_subsys.query', [['host_id', '=', id_]])}
        if host_subsys_ids:
            if force:
                await self.middleware.call('nvmet.host_subsys.delete_ids', list(host_subsys_ids))
            else:
                count = len(host_subsys_ids)
                if count == 1:
                    name = list(host_subsys_ids.values())[0]
                    verrors.add('nvmet_host_delete.id',
                                f'Host {host["hostnqn"]} used by 1 subsystem: {name}')
                else:
                    names = list(host_subsys_ids.values())[:3]
                    postfix = ",..." if count > 3 else ""
                    verrors.add('nvmet_host_delete.id',
                                f'Host {host["hostnqn"]} used by {count} subsystems: {",".join(names)}{postfix}')
        verrors.check()

        rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)
        await self._service_change('nvmet', 'reload')
        return rv

    @private
    async def extend(self, data):
        data['dhchap_dhgroup'] = DHCHAP_DHGROUP.by_db(data['dhchap_dhgroup']).api
        data['dhchap_hash'] = DHCHAP_HASH.by_db(data['dhchap_hash']).api
        return data

    @private
    async def compress(self, data):
        if 'dhchap_dhgroup' in data:
            data['dhchap_dhgroup'] = DHCHAP_DHGROUP.by_api(data['dhchap_dhgroup']).db
        if 'dhchap_hash' in data:
            data['dhchap_hash'] = DHCHAP_HASH.by_api(data['dhchap_hash']).db
        return data

    async def __validate(self, verrors, data, schema_name, old=None):
        id_ = old['id'] if old else None
        await self._ensure_unique(verrors, schema_name, 'hostnqn', data['hostnqn'], id_)

        # Check any keys supplied
        for keyname in ['dhchap_key', 'dhchap_ctrl_key']:
            key = data.get(keyname)
            if key is not None:
                match key[:10]:
                    case 'DHHC-1:00:':
                        if key[-1] != ':':
                            verrors.add(f'{schema_name}.{keyname}',
                                        'Unexpected key termination.  Use "nvme gen-dhchap-key" to generate.')
                    case 'DHHC-1:01:':
                        if len(base64.b64decode(key.split(':')[2])) != 36:
                            verrors.add(f'{schema_name}.{keyname}', 'Expected key length of 32')
                    case 'DHHC-1:02:':
                        if len(base64.b64decode(key.split(':')[2])) != 52:
                            verrors.add(f'{schema_name}.{keyname}', 'Expected key length of 48')
                    case 'DHHC-1:03:':
                        if len(base64.b64decode(key.split(':')[2])) != 68:
                            verrors.add(f'{schema_name}.{keyname}', 'Expected key length of 64')
                    case _:
                        verrors.add(f'{schema_name}.{keyname}',
                                    'Unexpected key format.  Use "nvme gen-dhchap-key" to generate.')
