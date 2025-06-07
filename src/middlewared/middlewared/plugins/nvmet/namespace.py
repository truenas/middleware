import os
import pathlib
import subprocess
import uuid

import middlewared.sqlalchemy as sa
from asyncio import Lock
from middlewared.api import api_method
from middlewared.api.current import (NVMetNamespaceCreateArgs,
                                     NVMetNamespaceCreateResult,
                                     NVMetNamespaceDeleteArgs,
                                     NVMetNamespaceDeleteResult,
                                     NVMetNamespaceEntry,
                                     NVMetNamespaceUpdateArgs,
                                     NVMetNamespaceUpdateResult)
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import SharingService, ValidationErrors, private
from middlewared.service_exception import CallError, MatchNotFound
from .constants import NAMESPACE_DEVICE_TYPE
from .kernel import lock_namespace as kernel_lock_namespace
from .kernel import unlock_namespace as kernel_unlock_namespace
from .kernel import resize_namespace as kernel_resize_namespace

UUID_GENERATE_RETRIES = 10
NSID_SEARCH_RANGE = 0xFFFF  # This is much less than NSID, but good enough for practical purposes.
NSID_LOCK = Lock()


def remove_file(data: dict) -> bool:
    if data['device_type'] == 'FILE':
        try:
            os.unlink(data['device_path'])
        except FileNotFoundError:
            pass
        except Exception as e:
            return e
    return True


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
    nvmet_namespace_filesize = sa.Column(sa.Integer(), nullable=True)
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
        datastore_extend_fk = ['subsys']
        cli_private = True
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetNamespaceEntry

    @api_method(
        NVMetNamespaceCreateArgs,
        NVMetNamespaceCreateResult,
        audit='Create NVMe target namespace',
        audit_extended=lambda data: f"Subsys ID: {data['subsys_id']} device path: {data['device_path']}"
    )
    async def do_create(self, data):
        """
        Create a NVMe target namespace in a subsystem (`subsys`).

        This will expose the namespace to any hosts permitted to access the subsystem.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'nvmet_namespace_create')
        verrors.check()

        await self.middleware.call('nvmet.namespace.save_file', data, 'nvmet_namespace_create', verrors)
        verrors.check()

        async with NSID_LOCK:
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
        Update NVMe target namespace of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(self.__audit_summary(old))
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_namespace_update', old=old)
        verrors.check()

        await self.middleware.call('nvmet.namespace.save_file', new, 'nvmet_namespace_update', verrors, old)
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
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete NVMe target namespace of `id`.
        """
        remove = options.get('remove', False)
        data = await self.get_instance(id_)
        audit_callback(self.__audit_summary(data))

        if remove:
            delete = await self.middleware.run_in_thread(remove_file, data)
            if isinstance(delete, Exception):
                # exception type is caught and returned in the
                # event an unexpected error happens
                raise CallError(f'Failed to remove namespace file: {delete!r}')

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
    def save_file(self, data, schema_name, verrors, old=None):
        if data['device_type'] == 'FILE':
            path = data['device_path']
            dirs = '/'.join(path.split('/')[:-1])

            # create extent directories
            try:
                pathlib.Path(dirs).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise CallError(
                    f'Failed to create {dirs} with error: {e}'
                )

            # create the file, or perhaps extend it
            if not os.path.exists(path):
                if _filesize := data.get('filesize'):
                    subprocess.run(['truncate', '-s', str(_filesize), path])
                else:
                    verrors.add(f'{schema_name}.filesize',
                                'Must supply filesize if device_path FILE does not exist.')
            else:
                if old:
                    if _new_size := data.get('filesize'):
                        old_size = int(old['filesize'])
                        new_size = int(_new_size)
                        # Only allow expansion
                        if new_size > old_size:
                            subprocess.run(['truncate', '-s', str(data['filesize']), path])
                            # resync so connected initiators can see the new size
                            self.middleware.call_sync('nvmet.namespace.resize_namespace', data['id'])
                        elif old_size > new_size:
                            verrors.add(f'{schema_name}.filesize',
                                        'Shrinking an namespace file is not allowed. This can lead to data loss.')

    @private
    def _is_dataset_path(self, pathstr: str) -> bool:
        if not pathstr.startswith('/mnt'):
            return False
        root_dev = os.stat('/mnt').st_dev
        path = pathlib.Path(pathstr)
        if path.exists():
            return path.stat().st_dev != root_dev
        elif path.parent.exists():
            return path.parent.stat().st_dev != root_dev
        else:
            return False

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
                if not self._is_dataset_path(device_path):
                    verrors.add(f'{schema_name}.device_path',
                                'FILE device_path must reside in an existing directory '
                                f'within volume mount point: {device_path}')
                elif os.path.isdir(device_path):
                    verrors.add(f'{schema_name}.device_path',
                                f'FILE device_path must not be a directory: {device_path}')
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
            existing_name = existing[0]['subsys']['name']
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
                    if key in ('enabled', 'filesize'):
                        continue
                    if data[key] == oldvalue:
                        continue
                    verrors.add(schema_name,
                                f'Cannot change {key} on an active namespace.  Disable first to allow change.')

        for key in ('device_uuid', 'device_nguid'):
            data[key] = await self.__generate_uuid(data.get(key), key)

    @private
    async def __generate_uuid(self, old_uuid, key):
        if old_uuid not in (None, ''):
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
        return f'{data["subsys"]["name"]}/{data["nsid"]}'

    async def __get_next_nsid(self, subsys_id):
        existing = {ns['nsid'] for ns in await self.middleware.call(f'{self._config.namespace}.query',
                                                                    [['subsys.id', '=', subsys_id]],
                                                                    {'select': ['nsid']})}

        for i in range(1, NSID_SEARCH_RANGE):
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
    async def resize_namespace(self, id_):
        data = await self.get_instance(id_)
        if data['enabled'] and await self.middleware.call('failover.status') in ('MASTER', 'SINGLE'):
            if (await self.middleware.call('nvmet.global.config'))['kernel']:
                await self.middleware.run_in_thread(kernel_resize_namespace, data)

    @private
    async def sharing_task_determine_locked(self, data):
        """Determine if this namespace is in a locked path"""
        return await self.middleware.call(
            'pool.dataset.path_in_locked_datasets',
            await self.get_path_field(data)
        )
