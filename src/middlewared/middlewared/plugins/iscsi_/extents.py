import hashlib
import os
import pathlib
import subprocess
import uuid
from collections import defaultdict

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    iSCSITargetExtentCreateArgs,
    iSCSITargetExtentCreateResult,
    iSCSITargetExtentDeleteArgs,
    iSCSITargetExtentDeleteResult,
    iSCSITargetExtentDiskChoicesArgs,
    iSCSITargetExtentDiskChoicesResult,
    iSCSITargetExtentEntry,
    iSCSITargetExtentUpdateArgs,
    iSCSITargetExtentUpdateResult
)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.service import CallError, SharingService, ValidationErrors, private
from middlewared.utils import secrets
from middlewared.utils.size import format_size
from .utils import sanitize_extent

EXTENT_DEFAULT_VENDOR = 'TrueNAS'
EXTENT_DEFAULT_PRODUCT_ID = 'iSCSI Disk'


def remove_extent_file(data: dict) -> str | bool:
    if data['type'] == 'FILE':
        try:
            os.unlink(data['path'])
        except FileNotFoundError:
            pass
        except Exception as e:
            return e

    return True


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
    iscsi_target_extent_product_id = sa.Column(sa.Text(), nullable=True)


class iSCSITargetExtentService(SharingService):

    share_task_type = 'iSCSI Extent'

    class Config:
        namespace = 'iscsi.extent'
        datastore = 'services.iscsitargetextent'
        datastore_prefix = 'iscsi_target_extent_'
        datastore_extend = 'iscsi.extent.extend'
        cli_namespace = 'sharing.iscsi.extent'
        role_prefix = 'SHARING_ISCSI_EXTENT'
        entry = iSCSITargetExtentEntry

    @private
    async def sharing_task_determine_locked(self, data):
        """Determine if this extent is in a locked path"""
        path = await self.get_path_field(data)
        if data['type'] == 'FILE':
            for component in pathlib.Path(path.removeprefix('/mnt/')).parents:
                c = component.as_posix()
                # walk up the path starting from right to left
                # if the component of the path isn't a valid
                # zfs filesystem name, then we make the
                # assumption that it _CANT_ be a filesystem
                # and so we move up to the next path.
                if validate_dataset_name(c):
                    return await self.middleware.call(
                        'pool.dataset.path_in_locked_datasets',
                        c
                    )
        return await self.middleware.call(
            'pool.dataset.path_in_locked_datasets',
            path
        )

    @api_method(
        iSCSITargetExtentCreateArgs,
        iSCSITargetExtentCreateResult,
        audit='Create iSCSI extent',
        audit_extended=lambda data: data['name']
    )
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
        await self.validate(data)
        verrors = ValidationErrors()
        await self.clean(data, 'iscsi_extent_create', verrors)
        verrors.check()

        await self.middleware.call('iscsi.extent.save', data, 'iscsi_extent_create', verrors)

        # This change is being made in conjunction with threads_num being specified in scst.conf
        if data['type'] == 'DISK' and data['path'].startswith('zvol/'):
            zvolname = zvol_path_to_name(os.path.join('/dev', data['path']))
            await self.middleware.call(
                'pool.dataset.update_impl',
                UpdateImplArgs(
                    name=zvolname,
                    zprops={'volthreading': 'off', 'readonly': 'on' if data['ro'] else 'off'}
                )
            )

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, {**data, 'vendor': EXTENT_DEFAULT_VENDOR},
            {'prefix': self._config.datastore_prefix}
        )

        return await self.get_instance(data['id'])

    @api_method(
        iSCSITargetExtentUpdateArgs,
        iSCSITargetExtentUpdateResult,
        audit='Update iSCSI extent',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI Extent of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id_)
        audit_callback(old['name'])

        new = old.copy()
        new.update(data)

        await self.middleware.call('iscsi.extent.validate', new)
        await self.clean(new, 'iscsi_extent_update', verrors, old=old)
        verrors.check()

        await self.middleware.call('iscsi.extent.save', new, 'iscsi_extent_create', verrors, old)
        verrors.check()
        new.pop(self.locked_field)

        zvolpath = new.get('path')
        if zvolpath is not None and zvolpath.startswith('zvol/'):
            zvolname = zvol_path_to_name(os.path.join('/dev', zvolpath))
            await self.middleware.call(
                'pool.dataset.update_impl',
                UpdateImplArgs(
                    name=zvolname,
                    zprops={'readonly': 'on' if new['ro'] else 'off'}
                )
            )

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        # scstadmin can have issues when modifying an existing extent, re-run
        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @api_method(
        iSCSITargetExtentDeleteArgs,
        iSCSITargetExtentDeleteResult,
        audit='Delete iSCSI extent',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, remove, force):
        """
        Delete iSCSI Extent of `id`.

        If `id` iSCSI Extent's `type` was configured to FILE, `remove` can be set to remove the configured file.
        """
        data = await self.get_instance(id_)
        audit_callback(data['name'])
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
            delete = await self.middleware.run_in_thread(remove_extent_file, data)
            if isinstance(delete, Exception):
                # exception type is caught and returned in the
                # event an unexpected error happens
                raise CallError(f'Failed to remove extent file: {delete!r}')

        for target_to_extent in target_to_extents:
            await self.middleware.call('iscsi.targetextent.delete', target_to_extent['id'], force)

        # This change is being made in conjunction with threads_num being specified in scst.conf
        if data['type'] == 'DISK' and data['path'].startswith('zvol/'):
            zvolname = zvol_path_to_name(os.path.join('/dev', data['path']))
            if zvol := await self.call2(
                self.s.zfs.resource.query_impl,
                {'paths': [zvolname], 'properties': ['volthreading']}
            ):
                if (
                    zvol[0]['type'] == 'VOLUME'
                    and zvol[0]['properties']['volthreading']['raw'] == 'off'
                ):
                    # Only try to set volthreading if:
                    # 1. volume still exists
                    # 2. is a volume
                    # 3. volthreading is currently off
                    await self.middleware.call(
                        'pool.dataset.update_impl',
                        UpdateImplArgs(
                            name=zvolname,
                            zprops={'volthreading': 'on'}
                        )
                    )

        try:
            return await self.middleware.call(
                'datastore.delete', self._config.datastore, id_
            )
        finally:
            await self._service_change('iscsitarget', 'reload')
            if all([await self.middleware.call("iscsi.global.alua_enabled"),
                    await self.middleware.call('failover.remote_connected')]):
                await self.middleware.call('iscsi.alua.wait_for_alua_settled')

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

        if not data['product_id']:
            data['product_id'] = EXTENT_DEFAULT_PRODUCT_ID

        return data

    @private
    async def clean(self, data, schema_name, verrors, old=None):
        await self.clean_name(data, schema_name, verrors, old=old)
        await self.clean_serial(data, schema_name, verrors, old=old)
        await self.middleware.call('iscsi.extent.clean_type_and_path', data, schema_name, verrors, old)
        await self.middleware.call('iscsi.extent.clean_size', data, schema_name, verrors)

    @private
    async def clean_name(self, data, schema_name, verrors, old=None):
        old_id = old['id'] if old else None
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
            else:
                # We can't *just* compare the names, because names get
                # flattened using sanitize_extent.  However, we'll preserve
                # the above check as-is so that we can be precise wrt the
                # error message given.
                if old_id:
                    name_filters = [('id', '!=', old_id)]
                else:
                    name_filters = []
                extents = await self.middleware.call(
                    'datastore.query',
                    self._config.datastore,
                    name_filters,
                    {'prefix': self._config.datastore_prefix}
                )
                name_to_fname = {sanitize_extent(ext['name']): ext['name'] for ext in extents}
                sname = sanitize_extent(name)
                if sname in name_to_fname:
                    clash = name_to_fname[sname]
                    verrors.add(f'{schema_name}.name', f'Extent name must be unique when flattened ({clash})')

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
    def clean_type_and_path(self, data, schema_name, verrors, old=None):
        not_old_id = ('id', '!=', old['id']) if old else None
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

            if namespaces := self.middleware.call_sync('nvmet.namespace.query', [['device_path', '=', disk]]):
                ns = namespaces[0]
                verrors.add(f'{schema_name}.disk',
                            f'Disk currently in use by NVMe-oF subsystem {ns["subsys"]["name"]} NSID {ns["nsid"]}')
                raise verrors

            device = os.path.join('/dev', disk)

            zvol_name = zvol_path_to_name(device)
            if not os.path.exists(device):
                verrors.add(f'{schema_name}.disk', f'Device {device!r} for volume {zvol_name!r} does not exist')

            self.middleware.call_sync('iscsi.extent.validate_zvol_path', verrors, f'{schema_name}.disk', device)

            if '@' in zvol_name and not data['ro']:
                verrors.add(f'{schema_name}.ro', 'Must be set when disk is a ZFS Snapshot')

            filters = [('disk', '=', disk)]
            if not_old_id:
                filters.append(not_old_id)
            if used := self.middleware.call_sync('iscsi.extent.query', filters, {'select': ['name']}):
                verrors.add(f'{schema_name}.disk',
                            f'Disk currently in use by extent {used[0]["name"]}')

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

            if ' ' in path:
                verrors.add(
                    f'{schema_name}.path',
                    'Filepath may not contain space characters'
                )

            if namespaces := self.middleware.call_sync('nvmet.namespace.query', [['device_path', '=', path]]):
                ns = namespaces[0]
                verrors.add(f'{schema_name}.path',
                            f'File currently in use by NVMe-oF subsystem {ns["subsys"]["name"]} NSID {ns["nsid"]}')
                raise verrors

            filters = [('path', '=', path)]
            if not_old_id:
                filters.append(not_old_id)
            if used := self.middleware.call_sync('iscsi.extent.query', filters, {'select': ['name']}):
                verrors.add(f'{schema_name}.path',
                            f'File currently in use by extent {used[0]["name"]}')

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
    async def extent_serial(self, serial):
        if serial in [None, '']:
            used_serials = [i['serial'] for i in (
                await self.middleware.call('iscsi.extent.query', [], {'select': ['serial']})
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

    @api_method(iSCSITargetExtentDiskChoicesArgs, iSCSITargetExtentDiskChoicesResult)
    async def disk_choices(self):
        """
        Return a dict of available zvols that can be used
        when creating an extent.
        """
        diskchoices = {}

        for zvol in await self.call2(
            self.middleware.services.zfs.resource.unlocked_zvols_fast,
            [['attachment', '=', None]],
            {},
            ['SIZE', 'RO', 'ATTACHMENT']
        ):
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

        target_to_id = {t['name']: t['id'] for t in await self.middleware.call('iscsi.target.query',
                                                                               [],
                                                                               {'select': ['id', 'name']})}
        extents = {e['id']: e for e in await self.middleware.call('iscsi.extent.query',
                                                                  [],
                                                                  {'select': ['id', 'name', 'locked']})}
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
        ha_basename_len = len(ha_basename)

        for iqn in filter(lambda x: x.startswith(ha_basename), iqns):
            target_name = iqn[ha_basename_len:]
            target_id = target_to_id[target_name]
            for ctl in iqns[iqn]:
                lun = int(ctl.split(':')[-1])
                for (l, extent_name) in target_luns[target_id]:
                    if l == lun:
                        result[extent_name] = ctl
                        break
        return result

    @private
    async def logged_in_extent(self, iqn, lun):
        """Return the device name (e.g. 13:0:0:0) of the logged in IQN/lun"""
        p = pathlib.Path('/sys/devices/platform')
        for targetname in p.glob('host*/session*/iscsi_session/session*/targetname'):
            logged_in_iqn = targetname.read_text().strip()
            if logged_in_iqn == iqn:
                for disk in targetname.parent.glob('device/target*/*/scsi_disk'):
                    device = disk.parent.name
                    if device.split(':')[-1] == str(lun):
                        return device
        return None

    @private
    async def active_extents(self):
        """
        Returns the names of all extents who are neither disabled nor locked, and which are
        associated with a target.
        """
        filters = [['enabled', '=', True], ['locked', '=', False]]
        extents = await self.middleware.call('iscsi.extent.query', filters, {'select': ['id', 'name']})
        assoc = [a_tgt['extent'] for a_tgt in await self.middleware.call('iscsi.targetextent.query')]
        result = []
        for extent in extents:
            if extent['id'] in assoc:
                result.append(extent['name'])
        return result

    @private
    async def pool_import(self, pool=None):
        """
        On pool import we will ensure that any ZVOLs used as iSCSI extents have the
        necessary properties set (i.e. turn off volthreading).
        """
        filters = [['type', '=', 'DISK']]
        if pool is not None:
            filters.append(['path', '^', f'zvol/{pool["name"]}/'])

        zvols = [
            extent['path'][5:] for extent in await self.middleware.call(
                'iscsi.extent.query',
                filters,
                {'select': ['path']}
            )
        ]
        if not zvols:
            return

        args = {'paths': zvols, 'properties': ['volthreading']}
        for zvol in await self.call2(self.s.zfs.resource.query_impl, args):
            if zvol['properties']['volthreading']['raw'] == 'on':
                await self.middleware.call(
                    'pool.dataset.update_impl',
                    UpdateImplArgs(
                        name=zvol['name'],
                        zprops={'volthreading': 'off'}
                    )
                )


async def pool_post_import(middleware, pool):
    await middleware.call('iscsi.extent.pool_import', pool)


async def setup(middleware):
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
