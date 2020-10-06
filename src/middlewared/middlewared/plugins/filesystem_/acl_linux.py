import errno
import enum
import os
import subprocess
import stat as pystat

from middlewared.schema import Bool, Dict, Int, List, Str, UnixPerm, accepts
from middlewared.service import private, CallError, Service, job
from middlewared.utils import osc
from middlewared.plugins.smb import SMBBuiltin
from middlewared.plugins.filesystem import ACLType


class ACLDefault(enum.Enum):
    OPEN = {'visible': True, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'everyone@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        }
    ]}
    RESTRICTED = {'visible': True, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
    ]}
    HOME = {'visible': True, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'NOINHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'everyone@',
            'id': None,
            'perms': {'BASIC': 'TRAVERSE'},
            'flags': {'BASIC': 'NOINHERIT'},
            'type': 'ALLOW'
        },
    ]}
    DOMAIN_HOME = {'visible': False, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {
                'DIRECTORY_INHERIT': True,
                'INHERIT_ONLY': True,
                'NO_PROPAGATE_INHERIT': True
            },
            'type': 'ALLOW'
        },
        {
            'tag': 'everyone@',
            'id': None,
            'perms': {'BASIC': 'TRAVERSE'},
            'flags': {'BASIC': 'NOINHERIT'},
            'type': 'ALLOW'
        }
    ]}


class FilesystemService(Service):

    @private
    def acltool(self, path, action, uid, gid, options):
        acltool = subprocess.run([
            '/usr/bin/acltool',
            '-a', action,
            '-O', str(uid), '-G', str(gid),
            '-rx' if options['traverse'] else '-r',
            '-c', path,
            '-p', path], check=False, capture_output=True
        )
        if acltool.returncode != 0:
            raise CallError(f"acltool [{action}] on path {path} failed with error: [{acltool.stderr.decode().strip()}]")

    def _common_perm_path_validate(self, path):
        if not os.path.exists(path):
            raise CallError(f"Path not found: {path}",
                            errno.ENOENT)

        if not os.path.realpath(path).startswith('/mnt/'):
            raise CallError(f"Changing permissions on paths outside of /mnt is not permitted: {path}",
                            errno.EPERM)

        if os.path.realpath(path) in [x['path'] for x in self.middleware.call_sync('pool.query')]:
            raise CallError(f"Changing permissions of root level dataset is not permitted: {path}",
                            errno.EPERM)

    @accepts(
        Dict(
            'filesystem_ownership',
            Str('path', required=True),
            Int('uid', null=True, default=None),
            Int('gid', null=True, default=None),
            Dict(
                'options',
                Bool('recursive', default=False),
                Bool('traverse', default=False)
            )
        )
    )
    @job(lock="perm_change")
    def chown(self, job, data):
        """
        Change owner or group of file at `path`.

        `uid` and `gid` specify new owner of the file. If either
        key is absent or None, then existing value on the file is not
        changed.

        `recursive` performs action recursively, but does
        not traverse filesystem mount points.

        If `traverse` and `recursive` are specified, then the chown
        operation will traverse filesystem mount points.
        """
        job.set_progress(0, 'Preparing to change owner.')

        self._common_perm_path_validate(data['path'])

        uid = -1 if data['uid'] is None else data['uid']
        gid = -1 if data['gid'] is None else data['gid']
        options = data['options']

        if not options['recursive']:
            job.set_progress(100, 'Finished changing owner.')
            os.chown(data['path'], uid, gid)
        else:
            if uid == -1 and gid == -1:
                return
            job.set_progress(10, f'Recursively changing owner of {data["path"]}.')
            # TODO: plumb in acltool to handle recursive / traverse so that we
            # don't break mountpoints
            # self.acltool(data['path'], 'chown', uid, gid, options)
            if gid == -1:
                chown = subprocess.run(['chown', '-R', str(uid), data['path']],
                                       check=False, capture_output=True)
            elif uid == -1:
                chown = subprocess.run(['chgrp', '-R', str(gid), data['path']],
                                       check=False, capture_output=True)
            else:
                chown = subprocess.run(['chown', '-R', f'{uid}:{gid}', data['path']],
                                       check=False, capture_output=True)

            if chown.returncode != 0:
                raise CallError(f"Failed to chown [{data['path']}]: "
                                f"{chown.stderr.decode()}")

            job.set_progress(100, 'Finished changing owner.')

    @accepts(
        Dict(
            'filesystem_permission',
            Str('path', required=True),
            UnixPerm('mode', null=True),
            Int('uid', null=True, default=None),
            Int('gid', null=True, default=None),
            Dict(
                'options',
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
            )
        )
    )
    @job(lock="perm_change")
    def setperm(self, job, data):
        """
        Remove extended ACL from specified path.

        If `mode` is specified then the mode will be applied to the
        path and files and subdirectories depending on which `options` are
        selected. Mode should be formatted as string representation of octal
        permissions bits.

        `uid` the desired UID of the file user. If set to None (the default), then user is not changed.

        `gid` the desired GID of the file group. If set to None (the default), then group is not changed.

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

        uid = -1 if data['uid'] is None else data['uid']
        gid = -1 if data['gid'] is None else data['gid']

        self._common_perm_path_validate(data['path'])

        acl_is_trivial = self.middleware.call_sync('filesystem.acl_is_trivial', data['path'])
        if not acl_is_trivial and not options['stripacl']:
            raise CallError(
                f'Non-trivial ACL present on [{data["path"]}]. Option "stripacl" required to change permission.',
                errno.EINVAL
            )

        if mode is not None:
            mode = int(mode, 8)

        stripacl = subprocess.run(['setfacl', '-b', data['path']],
                                  check=False, capture_output=True)
        if stripacl.returncode != 0:
            raise CallError(f"Failed to remove POSIX1e ACL from [{data['path']}]: "
                            f"{stripacl.stderr.decode()}")

        if mode:
            os.chmod(data['path'], mode)

        os.chown(data['path'], uid, gid)

        if not options['recursive']:
            job.set_progress(100, 'Finished setting permissions.')
            return

        action = 'clone' if mode else 'strip'
        job.set_progress(10, f'Recursively setting permissions on {data["path"]}.')
        if action == 'strip':
            stripacl = subprocess.run(['setfacl', '-bR', data['path']],
                                      check=False, capture_output=True)
            if stripacl.returncode != 0:
                raise CallError(f"Failed to remove POSIX1e ACL from [{data['path']}]: "
                                f"{stripacl.stderr.decode()}")

        if uid != -1 or gid != -1:
            if gid == -1:
                chown = subprocess.run(['chown', '-R', str(uid), data['path']],
                                       check=False, capture_output=True)
            elif uid == -1:
                chown = subprocess.run(['chgrp', '-R', str(gid), data['path']],
                                       check=False, capture_output=True)
            else:
                chown = subprocess.run(['chown', '-R', f'{uid}:{gid}', data['path']],
                                       check=False, capture_output=True)

            if chown.returncode != 0:
                raise CallError(f"Failed to chown [{data['path']}]: "
                                f"{chown.stderr.decode()}")

        chmod = subprocess.run(['chmod', '-R', str(data.get('mode')), data['path']],
                               check=False, capture_output=True)
        if chmod.returncode != 0:
            raise CallError(f"Failed to chmod [{data['path']}]: "
                            f"{chmod.stderr.decode()}")

        job.set_progress(100, 'Finished setting permissions.')

    @accepts()
    async def default_acl_choices(self):
        """
        Get list of default ACL types.
        """
        acl_choices = []
        for x in ACLDefault:
            if x.value['visible']:
                acl_choices.append(x.name)

        return acl_choices

    @accepts(
        Str('acl_type', default='OPEN', enum=[x.name for x in ACLDefault]),
        Str('share_type', default='NONE', enum=['NONE', 'AFP', 'SMB', 'NFS']),
    )
    async def get_default_acl(self, acl_type, share_type):
        """
        Returns a default ACL depending on the usage specified by `acl_type`.
        If an admin group is defined, then an entry granting it full control will
        be placed at the top of the ACL. Optionally may pass `share_type` to argument
        to get share-specific template ACL.
        """
        acl = []
        admin_group = (await self.middleware.call('smb.config'))['admin_group']
        if acl_type == 'HOME' and (await self.middleware.call('activedirectory.get_state')) == 'HEALTHY':
            acl_type = 'DOMAIN_HOME'
        if admin_group:
            acl.append({
                'tag': 'GROUP',
                'id': (await self.middleware.call('dscache.get_uncached_group', admin_group))['gr_gid'],
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            })
        if share_type == 'SMB':
            acl.append({
                'tag': 'GROUP',
                'id': int(SMBBuiltin['USERS'].value[1][9:]),
                'perms': {'BASIC': 'MODIFY'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            })
        acl.extend((ACLDefault[acl_type].value)['acl'])

        return acl

    @private
    def getacl_posix1e(self, path, simplified):
        st = os.stat(path)
        ret = {
            'uid': st.st_uid,
            'gid': st.st_gid,
            'acl': [],
            'flags': {
                'setuid': bool(st.st_mode & pystat.S_ISUID),
                'setgid': bool(st.st_mode & pystat.S_ISGID),
                'sticky': bool(st.st_mode & pystat.S_ISVTX),
            },
            'acltype': ACLType.POSIX1E.name
        }

        ret['uid'] = st.st_uid
        ret['gid'] = st.st_gid

        gfacl = subprocess.run(['getfacl', '-c' if osc.IS_LINUX else '-q', '-n', path],
                               check=False, capture_output=True)
        if gfacl.returncode != 0:
            raise CallError(f"Failed to get POSIX1e ACL on path [{path}]: {gfacl.stderr.decode()}")

        # linux output adds extra line to output if it's an absolute path and extra newline at end.
        entries = gfacl.stdout.decode().splitlines()
        entries = entries[:-1]

        for entry in entries:
            if entry.startswith("#"):
                continue
            ace = {
                "default": False,
                "tag": None,
                "id": -1,
                "perms": {
                    "READ": False,
                    "WRITE": False,
                    "EXECUTE": False,
                }
            }

            tag, id, perms = entry.rsplit(":", 2)
            ace['perms'].update({
                "READ": perms[0].casefold() == "r",
                "WRITE": perms[1].casefold() == "w",
                "EXECUTE": perms[2].casefold() == "x",
            })
            if tag.startswith('default'):
                ace['default'] = True
                tag = tag[8:]

            ace['tag'] = tag.upper()
            if id.isdigit():
                ace['id'] = int(id)
            ret['acl'].append(ace)

        return ret

    @accepts(
        Str('path'),
        Bool('simplified', default=True),
    )
    def getacl(self, path, simplified=True):
        """
        Return ACL of a given path. This may return a POSIX1e ACL or a NFSv4 ACL. The acl type is indicated
        by the `ACLType` key.

        Errata about ACLType NFSv4:

        `simplified` returns a shortened form of the ACL permset and flags.

        `TRAVERSE` sufficient rights to traverse a directory, but not read contents.

        `READ` sufficient rights to traverse a directory, and read file contents.

        `MODIFIY` sufficient rights to traverse, read, write, and modify a file. Equivalent to modify_set.

        `FULL_CONTROL` all permissions.

        If the permisssions do not fit within one of the pre-defined simplified permissions types, then
        the full ACL entry will be returned.

        In all cases we replace USER_OBJ, GROUP_OBJ, and EVERYONE with owner@, group@, everyone@ for
        consistency with getfacl and setfacl. If one of aforementioned special tags is used, 'id' must
        be set to None.

        An inheriting empty everyone@ ACE is appended to non-trivial ACLs in order to enforce Windows
        expectations regarding permissions inheritance. This entry is removed from NT ACL returned
        to SMB clients when 'ixnas' samba VFS module is enabled. We also remove it here to avoid confusion.
        """
        if not os.path.exists(path):
            raise CallError('Path not found.', errno.ENOENT)

        return self.getacl_posix1e(path, simplified)

    @private
    def setacl_nfs4(self, job, data):
        raise CallError('NFSv4 ACLs are not yet implemented.', errno.EOPNOTSUP)

    @private
    def setacl_posix1e(self, job, data):
        job.set_progress(0, 'Preparing to set acl.')
        if osc.IS_FREEBSD:
            raise CallError("POSIX1e brand ACLs not supported on the FreeBSD-based TrueNAS platform",
                            errno.EOPNOTSUPP)

        options = data['options']
        recursive = options.get('recursive')
        dacl = data.get('dacl', [])
        path = data['path']

        aclcheck = ACLType.POSIX1E.validate(data)

        if not aclcheck['is_valid']:
            raise CallError(f"POSIX1e ACL is invalid: {' '.join(aclcheck['errors'])}")

        stripacl = subprocess.run(['setfacl', '-bR' if recursive else '-b', path],
                                  check=False, capture_output=True)
        if stripacl.returncode != 0:
            raise CallError(f"Failed to remove POSIX1e ACL from [{path}]: "
                            f"{stripacl.stderr.decode()}")

        if options['stripacl']:
            job.set_progress(100, "Finished removing POSIX1e ACL")
            return

        job.set_progress(50, 'Reticulating splines.')

        for idx, ace in enumerate(dacl):
            if idx == 0:
                aclstring = ""
            else:
                aclstring += ","

            if ace['id'] == -1:
                ace['id'] = ''

            ace['tag'] = ace['tag'].rstrip('_OBJ').lower()

            if ace['default']:
                aclstring += "default:"

            aclstring += f"{ace['tag']}:{ace['id']}:"
            aclstring += 'r' if ace['perms']['READ'] else '-'
            aclstring += 'w' if ace['perms']['WRITE'] else '-'
            aclstring += 'x' if ace['perms']['EXECUTE'] else '-'

        setacl = subprocess.run(['setfacl', '-mR' if recursive else '-m', aclstring, path],
                                check=False, capture_output=True)
        if setacl.returncode != 0:
            return CallError(f'Failed to set ACL on path [{path}]: ',
                             f'{setacl.stderr.decode()}')

        job.set_progress(100, 'Finished setting POSIX1e ACL.')

    @accepts(
        Dict(
            'filesystem_acl',
            Str('path', required=True),
            Int('uid', null=True, default=None),
            Int('gid', null=True, default=None),
            List(
                'dacl',
                items=[
                    Dict(
                        'posix1e_ace',
                        Bool('default', default=False),
                        Str('tag', enum=['USER_OBJ', 'GROUP_OBJ', 'USER', 'GROUP', 'OTHER', 'MASK']),
                        Int('id', default=-1),
                        Dict(
                            'perms',
                            Bool('READ', default=False),
                            Bool('WRITE', default=False),
                            Bool('EXECUTE', default=False),
                        ),
                    )
                ],
                default=[]
            ),
            Str('acltype', enum=[x.name for x in ACLType], default=ACLType.POSIX1E.name),
            Dict(
                'options',
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
            )
        )
    )
    @job(lock="perm_change")
    def setacl(self, job, data):
        """
        Set ACL of a given path. Takes the following parameters:
        `path` full path to directory or file.

        `dacl` "simplified" ACL here or a full ACL.

        `uid` the desired UID of the file user. If set to None (the default), then user is not changed.

        `gid` the desired GID of the file group. If set to None (the default), then group is not changed.

        `recursive` apply the ACL recursively

        `traverse` traverse filestem boundaries (ZFS datasets)

        `strip` convert ACL to trivial. ACL is trivial if it can be expressed as a file mode without
        losing any access rules.

        `canonicalize` reorder ACL entries so that they are in concanical form as described
        in the Microsoft documentation MS-DTYP 2.4.5 (ACL)

        In all cases we replace USER_OBJ, GROUP_OBJ, and EVERYONE with owner@, group@, everyone@ for
        consistency with getfacl and setfacl. If one of aforementioned special tags is used, 'id' must
        be set to None.

        An inheriting empty everyone@ ACE is appended to non-trivial ACLs in order to enforce Windows
        expectations regarding permissions inheritance. This entry is removed from NT ACL returned
        to SMB clients when 'ixnas' samba VFS module is enabled.
        """
        acltype = ACLType[data['acltype']]
        if acltype == ACLType.NFS4:
            return self.setacl_nfs4(job, data)
        else:
            return self.setacl_posix1e(job, data)
