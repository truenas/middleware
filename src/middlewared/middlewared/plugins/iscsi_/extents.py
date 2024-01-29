import hashlib
import os
import pathlib
import secrets
import subprocess
import uuid

import middlewared.sqlalchemy as sa

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str
from middlewared.service import CallError, private, SharingService, ValidationErrors
from middlewared.utils.size import format_size
from middlewared.validators import Range
from collections import defaultdict

from .utils import MAX_EXTENT_NAME_LEN


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
        role_prefix = 'SHARING_ISCSI_EXTENT'

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
        if data['type'] == 'DISK' and any(path == os.path.join('/mnt', d['id']) for d in locked_datasets):
            return True

        return await self.middleware.call('pool.dataset.path_in_locked_datasets', path, locked_datasets)

    @accepts(Dict(
        'iscsi_extent_create',
        Str('name', required=True, max_length=MAX_EXTENT_NAME_LEN),
        Str('type', enum=['DISK', 'FILE'], default='DISK'),
        Str('disk', default=None, null=True),
        Str('serial', default=None, null=True),
        Str('path', default=None, null=True),
        Int('filesize', default=0),
        Int('blocksize', enum=[512, 1024, 2048, 4096], default=512),
        Bool('pblocksize'),
        Int('avail_threshold', validators=[Range(min_=1, max_=99)], null=True),
        Str('comment'),
        Bool('insecure_tpc', default=True),
        Bool('xen'),
        Str('rpm', enum=['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000'],
            default='SSD'),
        Bool('ro', default=False),
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
        await self.middleware.call('iscsi.extent.validate', data)
        await self.clean(data, 'iscsi_extent_create', verrors)
        verrors.check()

        await self.middleware.call('iscsi.extent.save', data, 'iscsi_extent_create', verrors)

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
    async def do_update(self, id_, data):
        """
        Update iSCSI Extent of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id_)

        new = old.copy()
        new.update(data)

        await self.middleware.call('iscsi.extent.validate', new)
        await self.clean(
            new, 'iscsi_extent_update', verrors, old=old
        )
        verrors.check()

        await self.middleware.call('iscsi.extent.save', new, 'iscsi_extent_create', verrors, old)
        verrors.check()
        new.pop(self.locked_field)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @accepts(
        Int('id'),
        Bool('remove', default=False),
        Bool('force', default=False),
    )
    async def do_delete(self, id_, remove, force):
        """
        Delete iSCSI Extent of `id`.

        If `id` iSCSI Extent's `type` was configured to FILE, `remove` can be set to remove the configured file.
        """
        data = await self.get_instance(id_)
        target_to_extents = await self.middleware.call('iscsi.targetextent.query', [['extent', '=', id_]])
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
                'datastore.delete', self._config.datastore, id_
            )
        finally:
            await self._service_change('iscsitarget', 'reload')

    @private
    def validate(self, data):
        data['serial'] = self.extent_serial(data['serial'])
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
        await self.clean_serial(data, schema_name, verrors, old=old)
        await self.middleware.call('iscsi.extent.clean_type_and_path', data, schema_name, verrors)
        await self.middleware.call('iscsi.extent.clean_size', data, schema_name, verrors)

    @private
    async def clean_name(self, data, schema_name, verrors, old=None):
        name = data['name']
        old = old['name'] if old is not None else None
        name_filters = [('name', '=', name)]

        if '"' in name:
            verrors.add(f'{schema_name}.name', 'Double quotes are not allowed')

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
    async def clean_serial(self, data, schema_name, verrors, old=None):
        serial = data['serial']
        old = old['serial'] if old is not None else None
        serial_filters = [('serial', '=', serial)]
        max_serial_len = 20  # SCST max length

        if '"' in serial:
            verrors.add(f'{schema_name}.serial', 'Double quotes are not allowed')

        if len(serial) > max_serial_len:
            verrors.add(
                f'{schema_name}.serial',
                f'Extent serial can not exceed {max_serial_len} characters'
            )

        if serial != old or old is None:
            serial_result = await self.middleware.call(
                'datastore.query',
                self._config.datastore,
                serial_filters,
                {'prefix': self._config.datastore_prefix}
            )
            if serial_result:
                verrors.add(f'{schema_name}.serial', 'Serial number must be unique')

    @private
    async def validate_path_resides_in_volume(self, verrors, schema, path):
        await check_path_resides_within_volume(verrors, self.middleware, schema, path)

    @private
    async def get_path_field(self, data):
        if data['type'] == 'DISK' and data[self.path_field].startswith('zvol/'):
            return os.path.join('/mnt', zvol_path_to_name(os.path.join('/dev', data[self.path_field])))

        return data[self.path_field]

    @private
    def clean_type_and_path(self, data, schema_name, verrors):
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

            if '@' in zvol_name and not data['ro']:
                verrors.add(f'{schema_name}.ro', 'Must be set when disk is a ZFS Snapshot')

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

            self.middleware.call_sync(
                'iscsi.extent.validate_path_resides_in_volume',
                verrors, f'{schema_name}.path', path
            )

        return data

    @private
    def clean_size(self, data, schema_name, verrors):
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
    def extent_serial(self, serial):
        if serial in [None, '']:
            used_serials = [i['serial'] for i in (
                self.middleware.call_sync('iscsi.extent.query', [], {'select': ['serial']})
            )]
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
    def save(self, data, schema_name, verrors, old=None):
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

            # create the extent, or perhaps extend it
            if not os.path.exists(path):
                # create the extent
                subprocess.run(['truncate', '-s', str(data['filesize']), path])
            else:
                if old:
                    old_size = int(old['filesize'])
                    new_size = int(data['filesize'])
                    # Only allow expansion
                    if new_size > old_size:
                        subprocess.run(['truncate', '-s', str(data['filesize']), path])
                        # resync so connected initiators can see the new size
                        self.middleware.call_sync('iscsi.global.resync_lun_size_for_file', path)
                    elif old_size > new_size:
                        verrors.add(f'{schema_name}.filesize',
                                    'Shrinking an extent is not allowed. This can lead to data loss.')

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

    @private
    async def logged_in_extents(self):
        """
        Obtain the unsurfaced disk names for all extents currently logged into on
        a HA STANDBY controller.

        :return: dict keyed by extent name, with unsurfaced disk name as the value
        """
        result = {}

        # First check if *anything* is logged in.
        iqns = await self.middleware.call('iscsi.target.logged_in_iqns')
        if not iqns:
            return result

        target_to_id = {t['name']: t['id'] for t in await self.middleware.call('iscsi.target.query', [], {'select': ['id', 'name']})}
        extents = {e['id']: e for e in await self.middleware.call('iscsi.extent.query', [], {'select': ['id', 'name', 'locked']})}
        assoc = await self.middleware.call('iscsi.targetextent.query')
        # Generate a dict, keyed by target ID whose value is a set of (lunID, extent name) tuples
        target_luns = defaultdict(set)
        for a_tgt in filter(
            lambda a: a['extent'] in extents and not extents[a['extent']]['locked'],
            assoc
        ):
            target_id = a_tgt['target']
            extent_name = extents[a_tgt['extent']]['name']
            target_luns[target_id].add((a_tgt['lunid'], extent_name))

        global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
        ha_basename = f'{global_basename}:HA:'

        for iqn in iqns:
            if not iqn.startswith(ha_basename):
                continue
            target_name = iqn.split(':')[-1]
            target_id = target_to_id[target_name]
            for ctl in iqns[iqn]:
                lun = int(ctl.split(':')[-1])
                for (l, extent_name) in target_luns[target_id]:
                    if l == lun:
                        result[extent_name] = ctl
                        break
        return result
