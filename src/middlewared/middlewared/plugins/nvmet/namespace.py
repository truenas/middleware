import os
import pathlib
import uuid

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetNamespaceCreateArgs, NVMetNamespaceCreateResult, NVMetNamespaceDeleteArgs,
                                     NVMetNamespaceDeleteResult, NVMetNamespaceEntry, NVMetNamespaceUpdateArgs,
                                     NVMetNamespaceUpdateResult)
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import SharingService, ValidationErrors, private
from middlewared.service_exception import CallError, MatchNotFound
from .constants import NAMESPACE_DEVICE_TYPE
from .kernel import lock_namespace as kernel_lock_namespace
from .kernel import unlock_namespace as kernel_unlock_namespace

UUID_GENERATE_RETRIES = 10


class NVMetNamespaceModel(sa.Model):
    __tablename__ = 'services_nvmet_namespace'
    __table_args__ = (
        sa.Index(
            'services_nvmet_namespace_nvmet_namespace_subsys_id__nvmet_namespace_nsid_uniq',
            'nvmet_namespace_subsys_id', 'nvmet_namespace_nsid', unique=True
        ),
    )

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_namespace_nsid = sa.Column(sa.Integer())
    nvmet_namespace_subsys_id = sa.Column(sa.ForeignKey('services_nvmet_subsys.id'), index=True)
    nvmet_namespace_device_type = sa.Column(sa.Integer())
    nvmet_namespace_device_path = sa.Column(sa.String(255), unique=True)
    nvmet_namespace_device_uuid = sa.Column(sa.String(40), unique=True)
    nvmet_namespace_device_nguid = sa.Column(sa.String(40), unique=True)
    nvmet_namespace_enabled = sa.Column(sa.Boolean())


class NVMetNamespaceService(SharingService):

    # For SharingService
    path_field = 'device_path'

    class Config:
        namespace = 'nvmet.namespace'
        datastore = 'services.nvmet_namespace'
        datastore_prefix = 'nvmet_namespace_'
        datastore_extend = 'nvmet.namespace.extend'
        cli_namespace = 'sharing.nvmet.namespace'
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetNamespaceEntry

    @api_method(
        NVMetNamespaceCreateArgs,
        NVMetNamespaceCreateResult,
        audit='Create NVMe target namespace',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_namespace_create')
        verrors.check()

        if not data.get('nsid'):
            data['nsid'] = await self.__get_next_nsid(data['subsys_id'])

        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(data['id'])

    @api_method(
        NVMetNamespaceUpdateArgs,
        NVMetNamespaceUpdateResult,
        audit='Update NVMe target namespace',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI Target of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(self.__audit_summary(old))
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_namespace_update', old=old)
        verrors.check()

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('nvmet', 'reload')
        return await self.get_instance(id_)

    @api_method(
        NVMetNamespaceDeleteArgs,
        NVMetNamespaceDeleteResult,
        audit='Delete NVMe target namespace',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_):
        data = await self.get_instance(id_)
        audit_callback(self.__audit_summary(data))

        rv = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await self._service_change('nvmet', 'reload')
        return rv

    @private
    async def extend(self, data):
        data['device_type'] = NAMESPACE_DEVICE_TYPE.by_db(data['device_type']).api
        return data

    @private
    async def compress(self, data):
        if 'device_type' in data:
            data['device_type'] = NAMESPACE_DEVICE_TYPE.by_api(data['device_type']).db
        if 'subsys' in data:
            # Foreign key subsys_id was expanded on query.  Compress again here.
            data['subsys_id'] = data['subsys']['id']
            del data['subsys']
        data.pop(self.locked_field, None)
        return data

    @private
    async def delete_ids(self, to_remove):
        # This is called internally (from nvmet.subsys.delete).  Does not require
        # a reload, because the caller will perform one
        return await self.middleware.call('datastore.delete', self._config.datastore, [['id', 'in', to_remove]])

    @private
    def clean_type_and_path(self, data, schema_name, verrors):
        device_type = data.get('device_type')
        device_path = data.get('device_path')

        match device_type:
            case 'ZVOL':
                if device_path.startswith('zvol/'):
                    zvol = pathlib.Path(zvol_name_to_path(device_path[5:]))
                    if not zvol.is_block_device():
                        verrors.add(f'{schema_name}.device_path',
                                    f'ZVOL device_path must be a block device: {device_path}')
                else:
                    verrors.add(f'{schema_name}.device_path',
                                f'ZVOL device_path must start with "zvol/": {device_path}')
            case 'FILE':
                if not device_path.startswith('/mnt/'):
                    verrors.add(f'{schema_name}.device_path',
                                f'FILE device_path must start with "/mnt/": {device_path}')
            case _:
                verrors.add(f'{schema_name}.device_type', 'Invalid device_type supplied')

    async def __validate(self, verrors, data, schema_name, old=None):
        try:
            # Create
            subsys_id = data['subsys_id']
        except KeyError:
            # Update - foreign keys get expanded
            subsys_id = data.get('subsys').get('id')

        nsid = data.get('nsid')

        # Ensure subsys_id exists
        try:
            await self.middleware.call('nvmet.subsys.query', [['id', '=', subsys_id]], {'get': True})
        except MatchNotFound:
            verrors.add(f'{schema_name}.subsys_id', f"No subsystem with ID {subsys_id}")

        # Ensure we're not making a duplicate
        _filter = [('nsid', '=', nsid), ('subsys_id', '=', subsys_id)]
        if old:
            _filter.append(('id', '!=', data['id']))
        if await self.query(_filter, {'force_sql_filters': True}):
            verrors.add(f'{schema_name}.nsid',
                        f"This record already exists (Subsystem ID: {subsys_id}/NSID: {nsid})")

        await self.middleware.call('nvmet.namespace.clean_type_and_path', data, schema_name, verrors)

        # Ensure we're not trying to use a device used elsewhere.
        # First check nvme.namespace
        _filter = [('device_path', '=', data.get('device_path'))]
        if old:
            _filter.append(('id', '!=', old['id']))
        existing = await self.query(_filter, {'force_sql_filters': True})
        if existing:
            existing_name = existing[0]['subsys']['nvmet_subsys_name']
            verrors.add(f'{schema_name}.device_path',
                        f"This device_path already used by subsystem: {existing_name}")
        # Next check iscsi.extent
        device_path = data.get('device_path')
        _filter = [
            ["OR",
             [
                 ["path", "=", device_path],
                 ["disk", "=", device_path]]]]
        existing = await self.middleware.call('iscsi.extent.query', _filter)
        if existing:
            existing_name = existing[0]['name']
            verrors.add(f'{schema_name}.device_path',
                        f"This device_path already used by iSCSI extent: {existing_name}")

        if old:
            # If the service is running then can only change items if disabled.
            # Except enabled flag.
            if old['enabled'] and await self.middleware.call('nvmet.global.running'):
                # Ensure we're only changing enabled
                for key, oldvalue in old.items():
                    if key == 'enabled':
                        continue
                    if data[key] == oldvalue:
                        continue
                    verrors.add(schema_name,
                                f'Cannot change {key} on an active namespace.  Disable first to allow change.')

        for key in ['device_uuid', 'device_nguid']:
            data[key] = await self.__generate_uuid(data.get(key), key)

    @private
    async def __generate_uuid(self, old_uuid, key):
        if old_uuid not in [None, '']:
            return old_uuid
        existing = [i[key] for i in (
            await self.middleware.call('nvmet.namespace.query', [], {'select': [key]})
        )]
        for i in range(UUID_GENERATE_RETRIES):
            new_uuid = str(uuid.uuid4())
            if new_uuid not in existing:
                return new_uuid
        raise CallError(f'Failed to generate a {key} for subsystem')

    def __audit_summary(self, data):
        return f'{data["subsys"]["nvmet_subsys_name"]}/{data["nsid"]}'

    async def __get_next_nsid(self, subsys_id):
        existing = {ns['nsid'] for ns in await self.middleware.call(f'{self._config.namespace}.query',
                                                                    [['subsys.id', '=', subsys_id]],
                                                                    {'select': ['nsid']})}

        for i in range(1, 32000):
            if i not in existing:
                return i
        raise ValueError("Unable to determine namespace ID (NSID)")

    @private
    async def get_path_field(self, data):
        """Required by SharingService."""
        if data['device_type'] == 'ZVOL' and data[self.path_field].startswith('zvol/'):
            return os.path.join('/mnt', zvol_path_to_name(os.path.join('/dev', data[self.path_field])))
        return data[self.path_field]

    @private
    async def stop(self, id_):
        data = await self.get_instance(id_)
        if data['enabled']:
            if (await self.middleware.call('nvmet.global.config'))['kernel']:
                await self.middleware.run_in_thread(kernel_lock_namespace, data)

    @private
    async def start(self, id_):
        data = await self.get_instance(id_)
        if data['enabled'] and await self.middleware.call('failover.status') in ('MASTER', 'SINGLE'):
            if (await self.middleware.call('nvmet.global.config'))['kernel']:
                await self.middleware.run_in_thread(kernel_unlock_namespace, data)

    @private
    async def sharing_task_determine_locked(self, data, locked_datasets):
        """
        `mountpoint` attribute of zvol will be unpopulated and so we
        first try direct comparison between the two strings.

        The parent dataset of a zvol may also be locked, which renders
        the zvol inaccessible as well, and so we need to continue to the
        common check for whether the path is in the locked datasets.
        """
        path = await self.get_path_field(data)
        if data['device_type'] == 'ZVOL' and any(path == os.path.join('/mnt', d['id']) for d in locked_datasets):
            return True

        return await self.middleware.call('pool.dataset.path_in_locked_datasets', path, locked_datasets)
