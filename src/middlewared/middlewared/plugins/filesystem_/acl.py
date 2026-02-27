import errno
import os
from pathlib import Path
from typing import Literal

import truenas_os

from pydantic import Field

from middlewared.api import api_method
from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args
from middlewared.api.current import (
    FilesystemGetaclArgs, FilesystemGetaclResult,
    FilesystemSetaclArgs, FilesystemSetaclResult,
    FilesystemChownArgs, FilesystemChownResult,
    FilesystemSetpermArgs, FilesystemSetpermResult,
    NFS4ACE, POSIXACE,
)
from middlewared.service import private, job, ValidationErrors, Service
from middlewared.service_exception import CallError, MatchNotFound, ValidationError
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    FS_ACL_Type,
    NFS4ACE_Tag,
    POSIXACE_Tag,
    NFS4ACE_MaskSimple,
    nfs4acl_dict_to_obj,
    nfs4acl_obj_to_dict,
    posixacl_dict_to_obj,
    posixacl_obj_to_dict,
    normalize_acl_ids,
    path_get_acltype,
    strip_acl_path,
)
from middlewared.utils.filesystem.directory import directory_is_empty
from middlewared.utils.path import FSLocation, path_location
from .utils import acltool, AclToolAction, calculate_inherited_acl


class SimplifiedAclEntry(BaseModel):
    id_type: Literal[NFS4ACE_Tag.USER, NFS4ACE_Tag.GROUP]
    id: int
    access: Literal[
        NFS4ACE_MaskSimple.READ,
        NFS4ACE_MaskSimple.MODIFY,
        NFS4ACE_MaskSimple.FULL_CONTROL
    ]


class FilesystemAddToAclOptions(BaseModel):
    force: bool = False


@single_argument_args('add_to_acl')
class FilesystemAddToAclArgs(BaseModel):
    path: NonEmptyString
    entries: list[SimplifiedAclEntry]
    options: FilesystemAddToAclOptions = Field(default=FilesystemAddToAclOptions())


class FilesystemAddToAclResult(BaseModel):
    result: bool


class FSGetInheritedAclOptions(BaseModel):
    directory: bool = True


@single_argument_args('calculate_inherited_acl')
class FilesystemGetInheritedAclArgs(BaseModel):
    path: NonEmptyString
    options: FSGetInheritedAclOptions = Field(default=FSGetInheritedAclOptions())


class FilesystemGetInheritedAclResult(BaseModel):
    result: list[NFS4ACE] | list[POSIXACE]


class FilesystemService(Service):

    class Config:
        cli_private = True

    def _common_perm_path_validate(self, schema, data, verrors, pool_mp_ok=False):
        loc = path_location(data['path'])
        if loc is FSLocation.EXTERNAL:
            verrors.add(f'{schema}.path', 'ACL operations on remote server paths are not possible')
            return loc

        path = data['path']

        try:
            st = self.middleware.call_sync('filesystem.stat', path)
        except CallError as e:
            if e.errno == errno.EINVAL:
                verrors.add('f{schema}.path', 'Must be an absolute path')
                return loc

            raise e

        if st['type'] == 'FILE' and data['options']['recursive']:
            verrors.add(f'{schema}.path', 'Recursive operations on a file are invalid.')
            return loc

        if st['is_ctldir']:
            verrors.add(f'{schema}.path',
                        'Permissions changes in ZFS control directory (.zfs) are not permitted')
            return loc

        if any(st['realpath'].startswith(prefix)
               for prefix in ('/home/admin/.ssh', '/home/truenas_admin/.ssh', '/root/.ssh')):
            return loc

        if not st['realpath'].startswith('/mnt/'):
            verrors.add(
                f'{schema}.path',
                "Changes to permissions on paths that are not beneath "
                f"the directory /mnt are not permitted: {path}"
            )

        elif len(Path(st['realpath']).resolve().parents) == 2:
            if not pool_mp_ok:
                verrors.add(
                    f'{schema}.path',
                    f'The specified path is a ZFS pool mountpoint "({path})" '
                )

        elif self.middleware.call_sync('pool.dataset.path_in_locked_datasets', st['realpath']):
            verrors.add(
                f'{schema}.path',
                'Path component is currently encrypted and locked'
            )
        else:
            statfs_flags = self.middleware.call_sync('filesystem.statfs', path)['flags']
            if 'RO' in statfs_flags:
                verrors.add(
                    f'{schema}.path',
                    f'{path}: dataset underlying path has the readonly property enabled.'
                )

        return loc

    @private
    def path_get_acltype(self, path):
        """
        Failure with ENODATA in case acltype is supported, but
        acl absent. EOPNOTSUPP means that acltype is not supported.

        raises NotImplementedError for EXTERNAL paths
        """

        if path_location(path) is FSLocation.EXTERNAL:
            raise NotImplementedError

        return path_get_acltype(path)

    @api_method(
        FilesystemChownArgs, FilesystemChownResult,
        roles=['FILESYSTEM_ATTRS_WRITE'],
        audit='Filesystem change owner', audit_extended=lambda data: data['path']
    )
    @job(lock="perm_change")
    def chown(self, job, data):
        """
        Change owner or group of file at `path`.

        `uid` and `gid` specify new owner of the file. If either
        key is absent or None, then existing value on the file is not
        changed.

        `user` and `group` alternatively allow specifying a uid gid by
        user name or group name.

        `recursive` performs action recursively, but does
        not traverse filesystem mount points.

        If `traverse` and `recursive` are specified, then the chown
        operation will traverse filesystem mount points.
        """
        job.set_progress(0, 'Preparing to change owner.')
        verrors = ValidationErrors()

        uid = -1 if data['uid'] is None else data.get('uid', -1)
        gid = -1 if data['gid'] is None else data.get('gid', -1)
        options = data['options']

        if data['user']:
            user = self.middleware.call_sync('user.query', [['username', '=', data['user']]])
            if user:
                uid = user[0]['uid']
            else:
                verrors.add('filesystem.chown.user', f'{data["user"]}: user does not exist')

        if data['group']:
            group = self.middleware.call_sync('group.query', [['group', '=', data['group']]])
            if group:
                gid = group[0]['gid']
            else:
                verrors.add('filesystem.chown.group', f'{data["group"]}: group does not exist')

        self._common_perm_path_validate("filesystem.chown", data, verrors)
        verrors.check()

        fd = truenas_os.openat2(
            data['path'], flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS
        )
        try:
            os.fchown(fd, uid, gid)
            if options['recursive']:
                job.set_progress(10, f'Recursively changing owner of {data["path"]}.')
                options['posixacl'] = True
                acltool(fd, AclToolAction.CHOWN, uid, gid, options, job)
        finally:
            os.close(fd)
        job.set_progress(100, 'Finished changing owner.')

    @api_method(
        FilesystemSetpermArgs, FilesystemSetpermResult,
        roles=['FILESYSTEM_ATTRS_WRITE'],
        audit='Filesystem set permission', audit_extended=lambda data: data['path']
    )
    @job(lock="perm_change")
    def setperm(self, job, data):
        """
        Set unix permissions on given `path`.

        If `mode` is specified then the mode will be applied to the
        path and files and subdirectories depending on which `options` are
        selected. Mode should be formatted as string representation of octal
        permissions bits.

        `uid` the desired UID of the file user. If set to None (the default), then user is not changed.

        `gid` the desired GID of the file group. If set to None (the default), then group is not changed.

        `user` and `group` alternatively allow specifying the owner by name.

        WARNING: `uid`, `gid, `user`, and `group` _should_ remain unset _unless_
        the administrator wishes to change the owner or group of files.

        `stripacl` setperm will fail if an extended ACL is present on `path`,
        unless `stripacl` is set to True.

        `recursive` remove ACLs recursively, but do not traverse dataset
        boundaries.

        `traverse` remove ACLs from child datasets.

        If no `mode` is set, and `stripacl` is True, then non-trivial ACLs
        will be converted to trivial ACLs. An ACL is trivial if it can be
        expressed as a file mode without losing any access rules.

        """
        job.set_progress(0, 'Preparing to set permissions.')
        options = data['options']
        mode = data.get('mode', None)
        verrors = ValidationErrors()

        uid = -1 if data['uid'] is None else data.get('uid', -1)
        gid = -1 if data['gid'] is None else data.get('gid', -1)

        if data['user']:
            user = self.middleware.call_sync('user.query', [['username', '=', data['user']]])
            if user:
                uid = user[0]['uid']
            else:
                verrors.add('filesystem.setperm.user', f'{data["user"]}: user does not exist')

        if data['group']:
            group = self.middleware.call_sync('group.query', [['group', '=', data['group']]])
            if group:
                gid = group[0]['gid']
            else:
                verrors.add('filesystem.setperm.group', f'{data["group"]}: group does not exist')

        self._common_perm_path_validate("filesystem.setperm", data, verrors)

        current_acl = self.middleware.call_sync('filesystem.getacl', data['path'])
        acl_is_trivial = current_acl['trivial']
        if not acl_is_trivial and not options['stripacl']:
            verrors.add(
                'filesystem.setperm.mode',
                f'Non-trivial ACL present on [{data["path"]}]. '
                'Option "stripacl" required to change permission.',
            )

        if mode is not None and int(mode, 8) == 0:
            verrors.add(
                'filesystem.setperm.mode',
                'Empty permissions are not permitted.'
            )

        verrors.check()
        is_nfs4acl = current_acl['acltype'] == 'NFS4'

        if mode is not None:
            mode = int(mode, 8)

        strip_acl_path(data['path'])

        fd = truenas_os.openat2(
            data['path'], flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS
        )
        try:
            if mode:
                os.fchmod(fd, mode)
            os.fchown(fd, uid, gid)
            if options['recursive']:
                action = AclToolAction.CLONE if mode else AclToolAction.STRIP
                job.set_progress(10, f'Recursively setting permissions on {data["path"]}.')
                options['posixacl'] = not is_nfs4acl
                options['do_chmod'] = True
                acltool(fd, action, uid, gid, options, job)
        finally:
            os.close(fd)
        job.set_progress(100, 'Finished setting permissions.')

    @private
    def getacl_nfs4(self, path, simplified, resolve_ids):
        fd = truenas_os.openat2(path, flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
        try:
            acl_obj = truenas_os.fgetacl(fd)
            st = os.fstat(fd)
        finally:
            os.close(fd)

        output = nfs4acl_obj_to_dict(acl_obj, st.st_uid, st.st_gid, simplified)
        output['path'] = path
        output['acltype'] = 'NFS4'

        for ace in output['acl']:
            if resolve_ids and ace['id'] != -1:
                ace['who'] = self.middleware.call_sync('idmap.id_to_name', ace['id'], ace['tag'])
            elif resolve_ids and ace['tag'] == 'group@':
                ace['who'] = self.middleware.call_sync('idmap.id_to_name', st.st_gid, 'GROUP')
            elif resolve_ids and ace['tag'] == 'owner@':
                ace['who'] = self.middleware.call_sync('idmap.id_to_name', st.st_uid, 'USER')
            elif resolve_ids:
                ace['who'] = None

        return output

    @private
    def getacl_posix1e(self, path, simplified, resolve_ids):
        fd = truenas_os.openat2(path, flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
        try:
            acl_obj = truenas_os.fgetacl(fd)
            st = os.fstat(fd)
        finally:
            os.close(fd)

        ret = posixacl_obj_to_dict(acl_obj, st.st_uid, st.st_gid)
        ret['acltype'] = FS_ACL_Type.POSIX1E
        ret['path'] = path

        for ace in ret['acl']:
            if resolve_ids and ace['id'] != -1:
                ace['who'] = self.middleware.call_sync('idmap.id_to_name', ace['id'], ace['tag'])
            elif resolve_ids and ace['tag'] == 'GROUP_OBJ':
                ace['who'] = self.middleware.call_sync('idmap.id_to_name', st.st_gid, 'GROUP')
            elif resolve_ids and ace['tag'] == 'USER_OBJ':
                ace['who'] = self.middleware.call_sync('idmap.id_to_name', st.st_uid, 'USER')
            elif resolve_ids:
                ace['who'] = None

        return ret

    @private
    def getacl_disabled(self, path):
        st = os.stat(path)
        return {
            'path': path,
            'uid': st.st_uid,
            'gid': st.st_gid,
            'acl': None,
            'acltype': FS_ACL_Type.DISABLED,
            'trivial': True,
        }

    @api_method(
        FilesystemGetaclArgs,
        FilesystemGetaclResult,
        roles=['FILESYSTEM_ATTRS_READ'],
    )
    def getacl(self, path, simplified, resolve_ids):
        """
        Return ACL of a given path. This may return a POSIX1e ACL or a NFSv4 ACL. The acl type is indicated
        by the `acltype` key.

        `simplified` - effect of this depends on ACL type on underlying filesystem. In the case of
        NFSv4 ACLs simplified permissions and flags are returned for ACL entries where applicable.
        NFSv4 errata below. In the case of POSIX1E ACls, this setting has no impact on returned ACL.

        `resolve_ids` - adds additional `who` key to each ACL entry, that converts the numeric id to
        a user name or group name. In the case of owner@ and group@ (NFSv4) or USER_OBJ and GROUP_OBJ
        (POSIX1E), st_uid or st_gid will be converted from stat() return for file. In the case of
        MASK (POSIX1E), OTHER (POSIX1E), everyone@ (NFSv4), key `who` will be included, but set to null.
        In case of failure to resolve the id to a name, `who` will be set to null. This option should
        only be used if resolving ids to names is required.

        Errata about ACLType NFSv4:

        `simplified` returns a shortened form of the ACL permset and flags where applicable. If permissions
        have been simplified, then the `perms` object will contain only a single `BASIC` key with a string
        describing the underlying permissions set.

        `TRAVERSE` sufficient rights to traverse a directory, but not read contents.

        `READ` sufficient rights to traverse a directory, and read file contents.

        `MODIFIY` sufficient rights to traverse, read, write, and modify a file.

        `FULL_CONTROL` all permissions.

        If the permisssions do not fit within one of the pre-defined simplified permissions types, then
        the full ACL entry will be returned.
        """
        if path_location(path) is FSLocation.EXTERNAL:
            raise CallError(f'{path} is external to TrueNAS', errno.EXDEV)

        if not os.path.exists(path):
            raise CallError('Path not found.', errno.ENOENT)

        acltype = path_get_acltype(path)

        if acltype == FS_ACL_Type.NFS4:
            ret = self.getacl_nfs4(path, simplified, resolve_ids)
        elif acltype == FS_ACL_Type.POSIX1E:
            ret = self.getacl_posix1e(path, simplified, resolve_ids)
        else:
            ret = self.getacl_disabled(path)

        ret.update({'user': None, 'group': None})

        if resolve_ids:
            if user := self.middleware.call_sync('user.query', [['uid', '=', ret['uid']]]):
                ret['user'] = user[0]['username']

            if group := self.middleware.call_sync('group.query', [['gid', '=', ret['gid']]]):
                ret['group'] = group[0]['group']

        return ret

    @private
    def setacl_nfs4(self, job, current_acl, data):
        job.set_progress(0, 'Preparing to set acl.')
        recursive = data['options'].get('recursive', False)
        do_strip = data['options'].get('stripacl', False)
        action = AclToolAction.CLONE

        verrors = ValidationErrors()
        job.set_progress(50, 'Setting NFSv4 ACL.')

        if do_strip:
            action = AclToolAction.STRIP
            strip_acl_path(data['path'])
        elif data['options']['validate_effective_acl']:
            uid_to_check = current_acl['uid'] if data['uid'] == ACL_UNDEFINED_ID else data['uid']
            gid_to_check = current_acl['gid'] if data['gid'] == ACL_UNDEFINED_ID else data['gid']
            self.middleware.call_sync(
                'filesystem.check_acl_execute',
                data['path'], data['dacl'], uid_to_check, gid_to_check, True
            )

        fd = truenas_os.openat2(
            data['path'], flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS
        )
        try:
            if not do_strip:
                try:
                    acl_obj = nfs4acl_dict_to_obj(data['dacl'], aclflags=None)
                except (ValueError, KeyError) as e:
                    verrors.add('filesystem_acl.dacl', str(e))
                    verrors.check()
                try:
                    truenas_os.validate_acl(fd, acl_obj)
                except ValueError as e:
                    verrors.add('filesystem_acl.dacl', str(e))
                    verrors.check()
                try:
                    truenas_os.fsetacl(fd, acl_obj)
                except (OSError, ValueError) as e:
                    raise CallError(str(e))

            os.fchown(fd, data['uid'], data['gid'])
            if recursive:
                acltool(fd, action, data['uid'], data['gid'], data['options'], job)
        finally:
            os.close(fd)

        job.set_progress(100, 'Finished setting NFSv4 ACL.')

    @private
    def setacl_posix1e(self, job, current_acl, data):
        job.set_progress(0, 'Preparing to set acl.')
        options = data['options']
        recursive = options.get('recursive', False)
        do_strip = options.get('stripacl', False)
        dacl = data.get('dacl', [])
        verrors = ValidationErrors()
        action = AclToolAction.STRIP if do_strip else AclToolAction.CLONE

        if do_strip and dacl:
            verrors.add(
                'filesystem_acl.dacl',
                'Simulatenously setting and removing ACL from path is invalid.'
            )

        if not do_strip:
            if options['validate_effective_acl']:
                try:
                    # check execute on parent paths
                    uid_to_check = current_acl['uid'] if data['uid'] == ACL_UNDEFINED_ID else data['uid']
                    gid_to_check = current_acl['gid'] if data['gid'] == ACL_UNDEFINED_ID else data['gid']

                    self.middleware.call_sync(
                        'filesystem.check_acl_execute',
                        data['path'], dacl, uid_to_check, gid_to_check, True
                    )
                except CallError as e:
                    if e.errno != errno.EPERM:
                        raise

                    verrors.add(
                        'filesystem_acl.path',
                        e.errmsg
                    )

        verrors.check()

        job.set_progress(50, 'Setting POSIX1e ACL.')

        acl_obj = None
        if do_strip:
            strip_acl_path(data['path'])
        else:
            try:
                acl_obj = posixacl_dict_to_obj(dacl)
            except (ValueError, KeyError) as e:
                raise CallError(f'Failed to build POSIX ACL for [{data["path"]}]: {e}')

        fd = truenas_os.openat2(
            data['path'], flags=os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS
        )
        try:
            if acl_obj is not None:
                try:
                    truenas_os.validate_acl(fd, acl_obj)
                except ValueError as e:
                    raise CallError(f'Failed to validate ACL for [{data["path"]}]: {e}')
                try:
                    truenas_os.fsetacl(fd, acl_obj)
                except (OSError, ValueError) as e:
                    raise CallError(f'Failed to set ACL on path [{data["path"]}]: {e}')

            os.fchown(fd, data['uid'], data['gid'])
            if recursive:
                options['posixacl'] = True
                acltool(fd, action, data['uid'], data['gid'], options, job)
        finally:
            os.close(fd)

        job.set_progress(100, 'Finished setting POSIX1e ACL.')

    @api_method(
        FilesystemSetaclArgs,
        FilesystemSetaclResult,
        roles=['FILESYSTEM_ATTRS_WRITE'],
        audit='Filesystem set ACL',
        audit_extended=lambda data: data['path']
    )
    @job(lock="perm_change")
    def setacl(self, job, data):
        """
        Set ACL of a given path. Takes the following parameters:
        `path` full path to directory or file.

        `dacl` ACL entries. Formatting depends on the underlying `acltype`. NFS4ACL requires
        NFSv4 entries. POSIX1e requires POSIX1e entries.

        `uid` the desired UID of the file user. If set to None (the default), then user is not changed.

        `user` the desired username for the file user. If set to None, then user is not changed.

        Note about interaction between `uid` and `user`:
        One and only one of these parameters should be set, and _only_ if the API consumer wishes to
        change the owner on the file / directory.

        `gid` the desired GID of the file group. If set to None (the default), then group is not changed.

        `group` the desired groupname for the file group. If set to None (the default), then group is not
        changed.

        Note about interaction between `gid` and `group`:
        One and only one of these parameters should be set, and _only_ if the API consumer wishes to
        change the owner on the file / directory.

        WARNING: if user, uid, group, or gid is specified in a recursive operation then the owning
        user, group, or both for _all_ files will be changed.

        `recursive` apply the ACL recursively

        `traverse` traverse filestem boundaries (ZFS datasets)

        `strip` convert ACL to trivial. ACL is trivial if it can be expressed as a file mode without
        losing any access rules.

        `canonicalize` deprecated, has no effect. ACL entries are always written in canonical order.

        The following notes about ACL entries are necessarily terse. If more detail is requried
        please consult relevant TrueNAS documentation.

        Notes about NFSv4 ACL entry fields:

        `tag` refers to the type of principal to whom the ACL entries applies. USER and GROUP have
        conventional meanings. `owner@` refers to the owning user of the file, `group@` refers to the owning
        group of the file, and `everyone@` refers to ALL users (including the owning user and group)..

        `id` refers to the numeric user id or group id associatiated with USER or GROUP entries.

        `who` a user or group name may be specified in lieu of numeric ID for USER or GROUP entries

        `type` may be ALLOW or DENY. Deny entries take precedence over allow when the ACL is evaluated.

        `perms` permissions allowed or denied by the entry. May be set as a simlified BASIC type or
        more complex type detailing specific permissions.

        `flags` inheritance flags determine how this entry will be presented (if at all) on newly-created
        files or directories within the specified path. Only valid for directories.

        Notes about posix1e ACL entry fields:

        `default` the ACL entry is in the posix default ACL (will be copied to new files and directories)
        created within the directory where it is set. These are _NOT_ evaluated when determining access for
        the file on which they're set. If default is false then the entry applies to the posix access ACL,
        which is used to determine access to the directory, but is not inherited on new files / directories.

        `tag` the type of principal to whom the ACL entry apples. USER and GROUP have conventional meanings
        USER_OBJ refers to the owning user of the file and is also denoted by "user" in conventional POSIX
        UGO permissions. GROUP_OBJ refers to the owning group of the file and is denoted by "group" in the
        same. OTHER refers to POSIX other, which applies to all users and groups who are not USER_OBJ or
        GROUP_OBJ. MASK sets maximum permissions granted to all USER and GROUP entries. A valid POSIX1 ACL
        entry contains precisely one USER_OBJ, GROUP_OBJ, OTHER, and MASK entry for the default and access
        list.

        `id` refers to the numeric user id or group id associatiated with USER or GROUP entries.

        `who` a user or group name may be specified in lieu of numeric ID for USER or GROUP entries

        `perms` - object containing posix permissions.
        """
        verrors = ValidationErrors()
        data['loc'] = self._common_perm_path_validate("filesystem.setacl", data, verrors)
        normalize_acl_ids(data)
        if data['uid'] != ACL_UNDEFINED_ID and data['user']:
            verrors.add(
                'filesystem.setacl.user',
                'User and uid may not be specified simultaneously.'
            )

        if data['gid'] != ACL_UNDEFINED_ID and data['group']:
            verrors.add(
                'filesystem.setacl.group',
                'group and gid may not be specified simultaneously.'
            )

        if data['user']:
            if user := self.middleware.call_sync('user.query', [['username', '=', data['user']]]):
                data['uid'] = user[0]['uid']
            else:
                verrors.add(
                    'filesystem.setacl.user',
                    f'{data["user"]}: user does not exist.'
                )

        if data['group']:
            if group := self.middleware.call_sync('group.query', [['group', '=', data['group']]]):
                data['gid'] = group[0]['gid']
            else:
                verrors.add(
                    'filesystem.setacl.group',
                    f'{data["group"]}: group does not exist.'
                )

        verrors.check()

        current_acl = self.getacl(data['path'])
        if data['acltype'] and data['acltype'] != current_acl['acltype']:
            raise ValidationError(
                'filesystem.setacl.dacl.acltype',
                'ACL type is invalid for selected path'
            )

        for idx, entry in enumerate(data['dacl']):
            # Convert any names to ids (because ultimately uid/gid is written to disk)
            # Earlier validation checks whether someone is trying to set both id and name.
            if entry.get('who') in (None, ''):
                # entry does not specify a name and so we don't need to normalize
                continue

            if entry.get('id') != ACL_UNDEFINED_ID:
                # entry already has a uid / gid
                continue

            # We're using user.query and group.query to intialize cache entries if required
            match entry['tag']:
                case 'USER':
                    method = 'user.query'
                    filters = [['username', '=', entry['who']]]
                    key = 'uid'
                case 'GROUP':
                    method = 'group.query'
                    filters = [['group', '=', entry['who']]]
                    key = 'gid'
                case POSIXACE_Tag.USER_OBJ | POSIXACE_Tag.GROUP_OBJ:
                    # We currently allow these because we're populating in getacl response
                    # This may need to be re-evaluated. These tags don't require an explicit uid/gid
                    # and so we can just skip safely
                    continue
                case NFS4ACE_Tag.SPECIAL_OWNER | NFS4ACE_Tag.SPECIAL_GROUP:
                    # We currently allow these because we're populating in getacl response
                    # This may need to be re-evaluated. These tags don't require an explicit uid/gid
                    # and so we can just skip safely
                    continue
                case _:
                    raise ValidationError(
                        f'filesystem.setacl.{idx}.who',
                        'Name may only be specified for USER and GROUP entries'
                    )
            try:
                entry['id'] = self.middleware.call_sync(method, filters, {'get': True})[key]
                entry['who'] = None
            except MatchNotFound:
                raise ValidationError(f'filesystem.setacl.{idx}.who', f'{entry["who"]}: account does not exist')

        match current_acl['acltype']:
            case FS_ACL_Type.NFS4:
                self.setacl_nfs4(job, current_acl, data)
            case FS_ACL_Type.POSIX1E:
                self.setacl_posix1e(job, current_acl, data)
            case FS_ACL_Type.DISABLED:
                raise CallError(f"{data['path']}: ACLs disabled on path.", errno.EOPNOTSUPP)
            case _:
                raise TypeError(f'{current_acl["acltype"]}: unexpected ACL type')

        return self.getacl(data['path'])

    @private
    def add_to_acl_posix(self, acl, entries):
        def convert_perm(perm):
            if perm == 'MODIFY' or perm == 'FULL_CONTROL':
                return {'READ': True, 'WRITE': True, 'EXECUTE': True}

            if perm == 'READ':
                return {'READ': True, 'WRITE': False, 'EXECUTE': True}

            raise CallError(f'{perm}: unsupported permissions type for POSIX1E acltype')

        def check_acl_for_entry(entry):
            id_type = entry['id_type']
            xid = entry['id']
            perm = entry['access']

            canonical_entries = {
                'USER_OBJ': {'has_default': False, 'entry': None},
                'GROUP_OBJ': {'has_default': False, 'entry': None},
                'OTHER': {'has_default': False, 'entry': None},
            }

            has_default = False
            has_access = False
            has_access_mask = False
            has_default_mask = False

            for ace in acl:
                if (centry := canonical_entries.get(ace['tag'])) is not None:
                    if ace['default']:
                        centry['has_default'] = True
                    else:
                        centry['entry'] = ace

                    continue

                if ace['tag'] == 'MASK':
                    if ace['default']:
                        has_default_mask = True
                    else:
                        has_access_mask = True

                    continue

                if ace['tag'] != id_type or ace['id'] != xid:
                    continue

                if ace['perms'] != convert_perm(perm):
                    continue

                if ace['default']:
                    has_default = True
                else:
                    has_access = True

            for key, val in canonical_entries.items():
                if val['has_default']:
                    continue

                acl.append({
                    'tag': key,
                    'id': val['entry']['id'],
                    'perms': val['entry']['perms'],
                    'default': True
                })

            return (has_default, has_access, has_access_mask, has_default_mask)

        def add_entry(entry, default):
            acl.append({
                'tag': entry['id_type'],
                'id': entry['id'],
                'perms': convert_perm(entry['access']),
                'default': default
            })

        def add_mask(default):
            acl.append({
                'tag': 'MASK',
                'id': -1,
                'perms': {'READ': True, 'WRITE': True, 'EXECUTE': True},
                'default': default
            })

        changed = False

        for entry in entries:
            default, access, mask, default_mask = check_acl_for_entry(entry)

            if not default:
                changed = True
                add_entry(entry, True)

            if not access:
                changed = True
                add_entry(entry, False)

            if not mask:
                changed = True
                add_mask(False)

            if not default_mask:
                changed = True
                add_mask(True)

        return changed

    @private
    def add_to_acl_nfs4(self, acl, entries):
        def convert_perm(perm):
            if perm == 'MODIFY':
                return {'BASIC': 'MODIFY'}

            if perm == 'READ':
                return {'BASIC': 'READ'}

            if perm == 'FULL_CONTROL':
                return {'BASIC': 'FULL_CONTROL'}

            raise CallError(f'{perm}: unsupported permissions type for NFSv4 acltype')

        def check_acl_for_entry(entry):
            id_type = entry['id_type']
            xid = entry['id']
            perm = entry['access']

            for ace in acl:
                if ace['tag'] != id_type or ace['id'] != xid or ace['type'] != 'ALLOW':
                    continue

                if ace['perms'].get('BASIC', {}) == perm:
                    return True

            return False

        changed = False

        for entry in entries:
            if check_acl_for_entry(entry):
                continue

            acl.append({
                'tag': entry['id_type'],
                'id': entry['id'],
                'perms': convert_perm(entry['access']),
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            })
            changed = True

        return changed

    @api_method(
        FilesystemAddToAclArgs,
        FilesystemAddToAclResult,
        audit='Filesystem add to ACL',
        audit_extended=lambda data: data['path'],
        private=True
    )
    @job()
    def add_to_acl(self, job, data):
        """
        Simplified ACL maintenance API for charts users to grant either read or
        modify access to particulr IDs on a given path. This call overwrites
        any existing ACL on the given path.

        `id_type` specifies whether the extra entry will be a user or group
        `id` specifies the numeric id of the user / group for which access is
        being granted.
        `access` specifies the simplified access mask to be granted to the user.
        For NFSv4 ACLs `READ` means the READ set, and `MODIFY` means the MODIFY
        set. For POSIX1E `READ` means read and execute, `MODIFY` means read, write,
        execute.
        """
        init_path = data['path']
        verrors = ValidationErrors()
        self._common_perm_path_validate('filesystem.add_to_acl', data, verrors)
        verrors.check()

        data['path'] = init_path
        current_acl = self.getacl(data['path'])
        acltype = FS_ACL_Type(current_acl['acltype'])

        if acltype == FS_ACL_Type.NFS4:
            changed = self.add_to_acl_nfs4(current_acl['acl'], data['entries'])
        elif acltype == FS_ACL_Type.POSIX1E:
            changed = self.add_to_acl_posix(current_acl['acl'], data['entries'])
        else:
            raise CallError(f"{data['path']}: ACLs disabled on path.", errno.EOPNOTSUPP)

        if not changed:
            job.set_progress(100, 'ACL already contains all requested entries.')
            return changed

        if not directory_is_empty(data['path']) and not data['options']['force']:
            raise CallError(
                f'{data["path"]}: path contains existing data '
                'and `force` was not specified', errno.EPERM
            )

        setacl_job = self.middleware.call_sync('filesystem.setacl', {
            'path': data['path'],
            'dacl': current_acl['acl'],
            'acltype': current_acl['acltype'],
            'options': {'recursive': True}
        })

        job.wrap_sync(setacl_job)
        return changed

    @api_method(FilesystemGetInheritedAclArgs, FilesystemGetInheritedAclResult, private=True)
    def get_inherited_acl(self, data):
        """
        Generate an inherited ACL based on given `path`
        Supports `directory` `option` that allows specifying whether the generated
        ACL is for a file or a directory.
        """
        verrors = ValidationErrors()
        self._common_perm_path_validate('filesystem.get_inherited_acl', data, verrors, True)
        verrors.check()

        current_acl = self.getacl(data['path'], False)
        return calculate_inherited_acl(current_acl, data['options']['directory'])
