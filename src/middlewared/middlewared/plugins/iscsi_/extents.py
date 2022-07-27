import hashlib
import os
import pathlib
import secrets
import uuid

import middlewared.sqlalchemy as sa

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str
from middlewared.service import CallError, private, SharingService, ValidationErrors
from middlewared.utils import run
from middlewared.utils.size import format_size
from middlewared.validators import Range


class iSCSITargetExtentModel(sa.Model):
    __tablename__ = 'services_iscsitargetextent'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_extent_name = sa.Column(sa.String(120), unique=True)
    iscsi_target_extent_serial = sa.Column(sa.String(16))
    iscsi_target_extent_type = sa.Column(sa.String(120))
    iscsi_target_extent_path = sa.Column(sa.String(120))
    iscsi_target_extent_filesize = sa.Column(sa.String(120), default=0)
    iscsi_target_extent_blocksize = sa.Column(sa.Integer(), default=512)
    iscsi_target_extent_pblocksize = sa.Column(sa.Boolean(), default=False)
    iscsi_target_extent_avail_threshold = sa.Column(sa.Integer(), nullable=True)
    iscsi_target_extent_comment = sa.Column(sa.String(120))
    iscsi_target_extent_naa = sa.Column(sa.String(34), unique=True)
    iscsi_target_extent_insecure_tpc = sa.Column(sa.Boolean(), default=True)
    iscsi_target_extent_xen = sa.Column(sa.Boolean(), default=False)
    iscsi_target_extent_rpm = sa.Column(sa.String(20), default='SSD')
    iscsi_target_extent_ro = sa.Column(sa.Boolean(), default=False)
    iscsi_target_extent_enabled = sa.Column(sa.Boolean(), default=True)
    iscsi_target_extent_vendor = sa.Column(sa.Text(), nullable=True)


class iSCSITargetExtentService(SharingService):

    share_task_type = 'iSCSI Extent'

    class Config:
        namespace = 'iscsi.extent'
        datastore = 'services.iscsitargetextent'
        datastore_prefix = 'iscsi_target_extent_'
        datastore_extend = 'iscsi.extent.extend'
        cli_namespace = 'sharing.iscsi.extent'

    @private
    async def sharing_task_datasets(self, data):
        if data['type'] == 'DISK':
            if data['path'].startswith('zvol/'):
                return [zvol_path_to_name(f'/dev/{data["path"]}')]
            else:
                return []

        return await super().sharing_task_datasets(data)

    @private
    async def sharing_task_determine_locked(self, data, locked_datasets):
        if data['type'] == 'DISK':
            if data['path'].startswith('zvol/'):
                return any(zvol_path_to_name(f'/dev/{data["path"]}') == d['id'] for d in locked_datasets)
            else:
                return False
        else:
            return await super().sharing_task_determine_locked(data, locked_datasets)

    @accepts(Dict(
        'iscsi_extent_create',
        Str('name', required=True),
        Str('type', enum=['DISK', 'FILE'], default='DISK'),
        Str('disk', default=None, null=True),
        Str('serial', default=None, null=True),
        Str('path', default=None, null=True),
        Int('filesize', default=0),
        Int('blocksize', enum=[512, 1024, 2048, 4096], default=512),
        Bool('pblocksize'),
        Int('avail_threshold', validators=[Range(min=1, max=99)], null=True),
        Str('comment'),
        Bool('insecure_tpc', default=True),
        Bool('xen'),
        Str('rpm', enum=['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000'],
            default='SSD'),
        Bool('ro'),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an iSCSI Extent.

        When `type` is set to FILE, attribute `filesize` is used and it represents number of bytes. `filesize` if
        not zero should be a multiple of `blocksize`. `path` is a required attribute with `type` set as FILE.

        With `type` being set to DISK, a valid ZFS volume is required.

        `insecure_tpc` when enabled allows an initiator to bypass normal access control and access any scannable
        target. This allows xcopy operations otherwise blocked by access control.

        `xen` is a boolean value which is set to true if Xen is being used as the iSCSI initiator.

        `ro` when set to true prevents the initiator from writing to this LUN.
        """
        verrors = ValidationErrors()
        await self.validate(data)
        await self.clean(data, 'iscsi_extent_create', verrors)
        verrors.check()

        await self.save(data, 'iscsi_extent_create', verrors)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, {**data, 'vendor': 'TrueNAS'},
            {'prefix': self._config.datastore_prefix}
        )

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'iscsi_extent_create',
            'iscsi_extent_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update iSCSI Extent of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.validate(new)
        await self.clean(
            new, 'iscsi_extent_update', verrors, old=old
        )
        verrors.check()

        await self.save(new, 'iscsi_extent_update', verrors)
        new.pop(self.locked_field)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id)

    @accepts(
        Int('id'),
        Bool('remove', default=False),
        Bool('force', default=False),
    )
    async def do_delete(self, id, remove, force):
        """
        Delete iSCSI Extent of `id`.

        If `id` iSCSI Extent's `type` was configured to FILE, `remove` can be set to remove the configured file.
        """
        data = await self.get_instance(id)
        target_to_extents = await self.middleware.call('iscsi.targetextent.query', [['extent', '=', id]])
        active_sessions = await self.middleware.call(
            'iscsi.target.active_sessions_for_targets', [t['target'] for t in target_to_extents]
        )
        if active_sessions:
            sessions_str = f'Associated target(s) {",".join(active_sessions)} ' \
                           f'{"is" if len(active_sessions) == 1 else "are"} in use.'
            if force:
                self.middleware.logger.warning('%s. Forcing deletion of extent.', sessions_str)
            else:
                raise CallError(sessions_str)

        if remove:
            delete = await self.remove_extent_file(data)

            if delete is not True:
                raise CallError('Failed to remove extent file')

        for target_to_extent in target_to_extents:
            await self.middleware.call('iscsi.targetextent.delete', target_to_extent['id'], force)

        try:
            return await self.middleware.call(
                'datastore.delete', self._config.datastore, id
            )
        finally:
            await self._service_change('iscsitarget', 'reload')

    @private
    async def validate(self, data):
        data['serial'] = await self.extent_serial(data['serial'])
        data['naa'] = self.extent_naa(data.get('naa'))

    @private
    async def extend(self, data):
        if data['type'] == 'DISK':
            data['disk'] = data['path']
        elif data['type'] == 'FILE':
            data['disk'] = None
            extent_size = data['filesize']
            # Legacy Compat for having 2[KB, MB, GB, etc] in database
            if not str(extent_size).isdigit():
                suffixes = {
                    'PB': 1125899906842624,
                    'TB': 1099511627776,
                    'GB': 1073741824,
                    'MB': 1048576,
                    'KB': 1024,
                    'B': 1
                }
                for x in suffixes.keys():
                    if str(extent_size).upper().endswith(x):
                        extent_size = str(extent_size).upper().strip(x)
                        extent_size = int(extent_size) * suffixes[x]

                        data['filesize'] = extent_size

        return data

    @private
    async def clean(self, data, schema_name, verrors, old=None):
        await self.clean_name(data, schema_name, verrors, old=old)
        await self.clean_type_and_path(data, schema_name, verrors)
        await self.clean_size(data, schema_name, verrors)

    @private
    async def clean_name(self, data, schema_name, verrors, old=None):
        name = data['name']
        old = old['name'] if old is not None else None
        serial = data['serial']
        name_filters = [('name', '=', name)]
        max_serial_len = 20  # SCST max length

        if '"' in name:
            verrors.add(f'{schema_name}.name', 'Double quotes are not allowed')

        if '"' in serial:
            verrors.add(f'{schema_name}.serial', 'Double quotes are not allowed')

        if len(serial) > max_serial_len:
            verrors.add(
                f'{schema_name}.serial',
                f'Extent serial can not exceed {max_serial_len} characters'
            )

        if name != old or old is None:
            name_result = await self.middleware.call(
                'datastore.query',
                self._config.datastore,
                name_filters,
                {'prefix': self._config.datastore_prefix}
            )
            if name_result:
                verrors.add(f'{schema_name}.name', 'Extent name must be unique')

    @private
    async def clean_type_and_path(self, data, schema_name, verrors):
        if data['type'] is None:
            return data

        extent_type = data['type']
        disk = data['disk']
        path = data['path']
        if extent_type == 'DISK':
            if not disk:
                verrors.add(f'{schema_name}.disk', 'This field is required')
                raise verrors

            if not disk.startswith('zvol/'):
                verrors.add(f'{schema_name}.disk', 'Disk name must start with "zvol/"')
                raise verrors

            device = os.path.join('/dev', disk)

            zvol_name = zvol_path_to_name(device)
            if not os.path.exists(device):
                verrors.add(f'{schema_name}.disk', f'Device {device!r} for volume {zvol_name!r} does not exist')

        elif extent_type == 'FILE':
            if not path:
                verrors.add(f'{schema_name}.path', 'This field is required')
                raise verrors  # They need this for anything else

            if os.path.exists(path):
                if not os.path.isfile(path) or path[-1] == '/':
                    verrors.add(
                        f'{schema_name}.path',
                        'You need to specify a filepath not a directory'
                    )

            await check_path_resides_within_volume(
                verrors, self.middleware, f'{schema_name}.path', path
            )

        return data

    @private
    async def clean_size(self, data, schema_name, verrors):
        # only applies to files
        if data['type'] != 'FILE':
            return data

        path = data['path']
        size = data['filesize']
        blocksize = data['blocksize']

        if not path:
            verrors.add(f'{schema_name}.path', 'This field is required')
        elif size == 0:
            if not os.path.exists(path) or not os.path.isfile(path):
                verrors.add(
                    f'{schema_name}.path',
                    'The file must exist if the extent size is set to auto (0)'
                )
        elif float(size) % blocksize:
            verrors.add(
                f'{schema_name}.filesize',
                f'File size ({size}) must be a multiple of block size ({blocksize})'
            )

        return data

    @private
    async def extent_serial(self, serial):
        if serial is None:
            used_serials = [i['serial'] for i in (await self.query())]
            tries = 5
            for i in range(tries):
                serial = secrets.token_hex()[:15]
                if serial not in used_serials:
                    break
                else:
                    if i < tries - 1:
                        continue
                    else:
                        raise CallError(
                            'Failed to generate a random extent serial'
                        )

        return serial

    @private
    def extent_naa(self, naa):
        if naa is None:
            return '0x6589cfc000000' + hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[0:19]
        else:
            return naa

    @accepts()
    async def disk_choices(self):
        """
        Return a dict of available zvols that can be used
        when creating an extent.
        """
        diskchoices = {}

        zvols = await self.middleware.call(
            'zfs.dataset.unlocked_zvols_fast',
            [['attachment', '=', None]], {},
            ['SIZE', 'RO', 'ATTACHMENT']
        )

        for zvol in zvols:
            key = os.path.relpath(zvol['path'], '/dev')
            if zvol['ro']:
                description = f'{zvol["name"]} [ro]'
            else:
                description = f'{zvol["name"]} ({format_size(zvol["size"])})'

            diskchoices[key] = description

        return diskchoices

    @private
    async def save(self, data, schema_name, verrors):
        if data['type'] == 'FILE':
            path = data['path']
            dirs = '/'.join(path.split('/')[:-1])

            # create extent directories
            try:
                pathlib.Path(dirs).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise CallError(
                    f'Failed to create {dirs} with error: {e}'
                )

            # create the extent
            if not os.path.exists(path):
                await run(['truncate', '-s', str(data['filesize']), path])

            data.pop('disk', None)
        else:
            data['path'] = data.pop('disk', None)

    @private
    async def remove_extent_file(self, data):
        if data['type'] == 'FILE':
            try:
                os.unlink(data['path'])
            except Exception as e:
                return e

        return True
