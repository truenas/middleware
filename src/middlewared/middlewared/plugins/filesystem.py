import binascii
try:
    import bsd
    from bsd import acl
except ImportError:
    bsd = acl = None
import errno
import enum
import grp
import os
import pwd
import select
import shutil
import subprocess
import stat as pystat

from middlewared.main import EventSource
from middlewared.schema import Bool, Dict, Int, Ref, List, Str, UnixPerm, accepts
from middlewared.service import private, CallError, Service, job
from middlewared.utils import filter_list, osc
from middlewared.plugins.smb import SMBBuiltin

OS_TYPE_FREEBSD = 0x01
OS_TYPE_LINUX = 0x02
OS_FLAG = int(osc.IS_FREEBSD) + (int(osc.IS_LINUX) << 1)


class ACLType(enum.Enum):
    NFS4 = (OS_TYPE_FREEBSD, ['tag', 'id', 'perms', 'flags', 'type'])
    POSIX1E = (OS_TYPE_FREEBSD | OS_TYPE_LINUX, ['default', 'tag', 'id', 'perms'])
    RICH = (OS_TYPE_LINUX,)
    SAMBA = (OS_TYPE_LINUX,)

    def validate(self, theacl):
        errors = []
        ace_keys = self.value[1]
        if not self.value[0] & OS_FLAG:
            errors.append("The host operating system does not support"
                          f"ACLType [{self.name}]")

        if self != ACLType.NFS4 and theacl.get('nfs41flags'):
            errors.append(f"NFS41 ACL flags are not valid for ACLType [{self.name}]")

        for idx, entry in enumerate(theacl['dacl']):
            extra = set(entry.keys()) - set(ace_keys)
            missing = set(ace_keys) - set(entry.keys())
            if extra:
                errors.append(f"ACL entry [{idx}] contains invalid extra key(s): {extra}")
            if missing:
                errors.append(f"ACL entry [{idx}] is missing required keys(s): {missing}")

        return {"is_valid": len(errors) == 0, "errors": errors}


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

    @accepts(Str('path', required=True), Ref('query-filters'), Ref('query-options'))
    def listdir(self, path, filters=None, options=None):
        """
        Get the contents of a directory.

        Each entry of the list consists of:
          name(str): name of the file
          path(str): absolute path of the entry
          realpath(str): absolute real path of the entry (if SYMLINK)
          type(str): DIRECTORY | FILESYSTEM | SYMLINK | OTHER
          size(int): size of the entry
          mode(int): file mode/permission
          uid(int): user id of entry owner
          gid(int): group id of entry onwer
          acl(bool): extended ACL is present on file
        """
        if not os.path.exists(path):
            raise CallError(f'Directory {path} does not exist', errno.ENOENT)

        if not os.path.isdir(path):
            raise CallError(f'Path {path} is not a directory', errno.ENOTDIR)

        rv = []
        for entry in os.scandir(path):
            if entry.is_symlink():
                etype = 'SYMLINK'
            elif entry.is_dir():
                etype = 'DIRECTORY'
            elif entry.is_file():
                etype = 'FILE'
            else:
                etype = 'OTHER'

            data = {
                'name': entry.name,
                'path': entry.path,
                'realpath': os.path.realpath(entry.path) if etype == 'SYMLINK' else entry.path,
                'type': etype,
            }
            try:
                stat = entry.stat()
                data.update({
                    'size': stat.st_size,
                    'mode': stat.st_mode,
                    'acl': False if self.acl_is_trivial(data["realpath"]) else True,
                    'uid': stat.st_uid,
                    'gid': stat.st_gid,
                })
            except FileNotFoundError:
                data.update({'size': None, 'mode': None, 'acl': None, 'uid': None, 'gid': None})
            rv.append(data)
        return filter_list(rv, filters=filters or [], options=options or {})

    @accepts(Str('path'))
    def stat(self, path):
        """
        Return the filesystem stat(2) for a given `path`.
        """
        try:
            stat = os.stat(path, follow_symlinks=False)
        except FileNotFoundError:
            raise CallError(f'Path {path} not found', errno.ENOENT)

        stat = {
            'size': stat.st_size,
            'mode': stat.st_mode,
            'uid': stat.st_uid,
            'gid': stat.st_gid,
            'atime': stat.st_atime,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime,
            'dev': stat.st_dev,
            'inode': stat.st_ino,
            'nlink': stat.st_nlink,
        }

        try:
            stat['user'] = pwd.getpwuid(stat['uid']).pw_name
        except KeyError:
            stat['user'] = None

        try:
            stat['group'] = grp.getgrgid(stat['gid']).gr_name
        except KeyError:
            stat['group'] = None

        stat['acl'] = False if self.acl_is_trivial(path) else True

        return stat

    @private
    @accepts(
        Str('path'),
        Str('content', max_length=2048000),
        Dict(
            'options',
            Bool('append', default=False),
            Int('mode'),
        ),
    )
    def file_receive(self, path, content, options=None):
        """
        Simplified file receiving method for small files.

        `content` must be a base 64 encoded file content.
        """
        options = options or {}
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if options.get('append'):
            openmode = 'ab'
        else:
            openmode = 'wb+'
        with open(path, openmode) as f:
            f.write(binascii.a2b_base64(content))
        mode = options.get('mode')
        if mode:
            os.chmod(path, mode)
        return True

    @private
    @accepts(
        Str('path'),
        Dict(
            'options',
            Int('offset'),
            Int('maxlen'),
        ),
    )
    def file_get_contents(self, path, options=None):
        """
        Get contents of a file `path` in base64 encode.

        DISCLAIMER: DO NOT USE THIS FOR BIG FILES (> 500KB).
        """
        options = options or {}
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            if options.get('offset'):
                f.seek(options['offset'])
            data = binascii.b2a_base64(f.read(options.get('maxlen'))).decode().strip()
        return data

    @accepts(Str('path'))
    @job(pipes=["output"])
    async def get(self, job, path):
        """
        Job to get contents of `path`.
        """

        if not os.path.isfile(path):
            raise CallError(f'{path} is not a file')

        with open(path, 'rb') as f:
            await self.middleware.run_in_thread(shutil.copyfileobj, f, job.pipes.output.w)

    @accepts(
        Str('path'),
        Dict(
            'options',
            Bool('append', default=False),
            Int('mode'),
        ),
    )
    @job(pipes=["input"])
    async def put(self, job, path, options=None):
        """
        Job to put contents to `path`.
        """
        options = options or {}
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if options.get('append'):
            openmode = 'ab'
        else:
            openmode = 'wb+'

        with open(path, openmode) as f:
            await self.middleware.run_in_thread(shutil.copyfileobj, job.pipes.input.r, f)

        mode = options.get('mode')
        if mode:
            os.chmod(path, mode)
        return True

    @accepts(Str('path'))
    def statfs(self, path):
        """
        Return stats from the filesystem of a given path.

        Raises:
            CallError(ENOENT) - Path not found
        """
        try:
            statfs = bsd.statfs(path)
        except FileNotFoundError:
            raise CallError('Path not found.', errno.ENOENT)
        return {
            **statfs.__getstate__(),
            'total_bytes': statfs.total_blocks * statfs.blocksize,
            'free_bytes': statfs.free_blocks * statfs.blocksize,
            'avail_bytes': statfs.avail_blocks * statfs.blocksize,
        }

    def __convert_to_basic_permset(self, permset):
        """
        Convert "advanced" ACL permset format to basic format using
        bitwise operation and constants defined in py-bsd/bsd/acl.pyx,
        py-bsd/defs.pxd and acl.h.

        If the advanced ACL can't be converted without losing
        information, we return 'OTHER'.

        Reverse process converts the constant's value to a dictionary
        using a bitwise operation.
        """
        perm = 0
        for k, v, in permset.items():
            if v:
                perm |= acl.NFS4Perm[k]

        try:
            SimplePerm = (acl.NFS4BasicPermset(perm)).name
        except Exception:
            SimplePerm = 'OTHER'

        return SimplePerm

    def __convert_to_basic_flagset(self, flagset):
        flags = 0
        for k, v, in flagset.items():
            if k == "INHERITED":
                continue
            if v:
                flags |= acl.NFS4Flag[k]

        try:
            SimpleFlag = (acl.NFS4BasicFlagset(flags)).name
        except Exception:
            SimpleFlag = 'OTHER'

        return SimpleFlag

    def __convert_to_adv_permset(self, basic_perm):
        permset = {}
        perm_mask = acl.NFS4BasicPermset[basic_perm].value
        for name, member in acl.NFS4Perm.__members__.items():
            if perm_mask & member.value:
                permset.update({name: True})
            else:
                permset.update({name: False})

        return permset

    def __convert_to_adv_flagset(self, basic_flag):
        flagset = {}
        flag_mask = acl.NFS4BasicFlagset[basic_flag].value
        for name, member in acl.NFS4Flag.__members__.items():
            if flag_mask & member.value:
                flagset.update({name: True})
            else:
                flagset.update({name: False})

        return flagset

    def _winacl(self, path, action, uid, gid, options):
        winacl = subprocess.run([
            '/usr/local/bin/winacl',
            '-a', action,
            '-O', str(uid), '-G', str(gid),
            '-rx' if options['traverse'] else '-r',
            '-c', path,
            '-p', path], check=False, capture_output=True
        )
        if winacl.returncode != 0:
            raise CallError(f"Winacl {action} on path {path} failed with error: [{winacl.stderr.decode().strip()}]")

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

    @accepts(Str('path'))
    def acl_is_trivial(self, path):
        """
        Returns True if the ACL can be fully expressed as a file mode without losing
        any access rules, or if the path does not support NFSv4 ACLs (for example
        a path on a tmpfs filesystem).
        """
        if not os.path.exists(path):
            raise CallError(f'Path not found [{path}].', errno.ENOENT)

        if osc.IS_LINUX:
            posix1e_acl = self.getacl_posix1e(path, True)
            return True if len(posix1e_acl['acl']) == 3 else False

        if not os.pathconf(path, 64):
            return True

        return acl.ACL(file=path).is_trivial

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
            job.set_progress(10, f'Recursively changing owner of {data["path"]}.')
            self._winacl(data['path'], 'chown', uid, gid, options)
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

        a = acl.ACL(file=data['path'])
        a.strip()
        a.apply(data['path'])

        if mode:
            os.chmod(data['path'], mode)

        if uid or gid:
            os.chown(data['path'], uid, gid)

        if not options['recursive']:
            job.set_progress(100, 'Finished setting permissions.')
            return

        action = 'clone' if mode else 'strip'
        job.set_progress(10, f'Recursively setting permissions on {data["path"]}.')
        self._winacl(data['path'], action, uid, gid, options)
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

    def _is_inheritable(self, flags):
        """
        Takes ACE flags and return True if any inheritance bits are set.
        """
        inheritance_flags = ['FILE_INHERIT', 'DIRECTORY_INHERIT', 'NO_PROPAGATE_INHERIT', 'INHERIT_ONLY']
        for i in inheritance_flags:
            if flags.get(i):
                return True

        return False

    @private
    def canonicalize_acl_order(self, acl):
        """
        Convert flags to advanced, then separate the ACL into two lists. One for ACEs that have been inherited,
        one for aces that have not been inherited. Non-inherited ACEs take precedence
        and so they are placed first in finalized combined list. Within each list, the
        ACEs are orderd according to the following:

        1) Deny ACEs that apply to the object itself (NOINHERIT)

        2) Deny ACEs that apply to a subobject of the object (INHERIT)

        3) Allow ACEs that apply to the object itself (NOINHERIT)

        4) Allow ACEs that apply to a subobject of the object (INHERIT)

        See http://docs.microsoft.com/en-us/windows/desktop/secauthz/order-of-aces-in-a-dacl

        The "INHERITED" bit is stripped in filesystem.getacl when generating a BASIC flag type.
        It is best practice to use a non-simplified ACL for canonicalization.
        """
        inherited_aces = []
        final_acl = []
        non_inherited_aces = []
        for entry in acl:
            entry['flags'] = self.__convert_to_adv_flagset(entry['flags']['BASIC']) if 'BASIC' in entry['flags'] else entry['flags']
            if entry['flags'].get('INHERITED'):
                inherited_aces.append(entry)
            else:
                non_inherited_aces.append(entry)

        if inherited_aces:
            inherited_aces = sorted(
                inherited_aces,
                key=lambda x: (x['type'] == 'ALLOW', self._is_inheritable(x['flags'])),
            )
        if non_inherited_aces:
            non_inherited_aces = sorted(
                non_inherited_aces,
                key=lambda x: (x['type'] == 'ALLOW', self._is_inheritable(x['flags'])),
            )
        final_acl = non_inherited_aces + inherited_aces
        return final_acl

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
        if osc.IS_LINUX:
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

    @private
    def getacl_nfs4(self, path, simplified):
        stat = os.stat(path)

        a = acl.ACL(file=path)
        fs_acl = a.__getstate__()

        if not simplified:
            advanced_acl = []
            for entry in fs_acl:
                ace = {
                    'tag': (acl.ACLWho[entry['tag']]).value,
                    'id': entry['id'],
                    'type': entry['type'],
                    'perms': entry['perms'],
                    'flags': entry['flags'],
                }
                if ace['tag'] == 'everyone@' and self.__convert_to_basic_permset(ace['perms']) == 'NOPERMS':
                    continue

                advanced_acl.append(ace)

            return {'uid': stat.st_uid, 'gid': stat.st_gid, 'acl': advanced_acl, 'acltype': ACLType.NFS4.name}

        simple_acl = []
        for entry in fs_acl:
            ace = {
                'tag': (acl.ACLWho[entry['tag']]).value,
                'id': entry['id'],
                'type': entry['type'],
                'perms': {'BASIC': self.__convert_to_basic_permset(entry['perms'])},
                'flags': {'BASIC': self.__convert_to_basic_flagset(entry['flags'])},
            }
            if ace['tag'] == 'everyone@' and ace['perms']['BASIC'] == 'NOPERMS':
                continue

            for key in ['perms', 'flags']:
                if ace[key]['BASIC'] == 'OTHER':
                    ace[key] = entry[key]

            simple_acl.append(ace)

        return {'uid': stat.st_uid, 'gid': stat.st_gid, 'acl': simple_acl, 'acltype': ACLType.NFS4.name}

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

        if osc.IS_LINUX or not os.pathconf(path, 64):
            return self.getacl_posix1e(path, simplified)

        return self.getacl_nfs4(path, simplified)

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

    @private
    def setacl_nfs4(self, job, data):
        job.set_progress(0, 'Preparing to set acl.')
        options = data['options']
        dacl = data.get('dacl', [])

        if osc.IS_LINUX or not os.pathconf(data['path'], 64):
            raise CallError(f"NFSv4 ACLS are not supported on path {data['path']}", errno.EOPNOTSUPP)

        self._common_perm_path_validate(data['path'])

        if dacl and options['stripacl']:
            raise CallError('Setting ACL and stripping ACL are not permitted simultaneously.', errno.EINVAL)

        uid = -1 if data.get('uid', None) is None else data['uid']
        gid = -1 if data.get('gid', None) is None else data['gid']
        if options['stripacl']:
            a = acl.ACL(file=data['path'])
            a.strip()
            a.apply(data['path'])
        else:
            inheritable_is_present = False
            cleaned_acl = []
            lockace_is_present = False
            for entry in dacl:
                ace = {
                    'tag': (acl.ACLWho(entry['tag'])).name,
                    'id': entry['id'],
                    'type': entry['type'],
                    'perms': self.__convert_to_adv_permset(entry['perms']['BASIC']) if 'BASIC' in entry['perms'] else entry['perms'],
                    'flags': self.__convert_to_adv_flagset(entry['flags']['BASIC']) if 'BASIC' in entry['flags'] else entry['flags'],
                }
                if ace['flags'].get('INHERIT_ONLY') and not ace['flags'].get('DIRECTORY_INHERIT', False) and not ace['flags'].get('FILE_INHERIT', False):
                    raise CallError(
                        'Invalid flag combination. DIRECTORY_INHERIT or FILE_INHERIT must be set if INHERIT_ONLY is set.',
                        errno.EINVAL
                    )
                if ace['tag'] == 'EVERYONE' and self.__convert_to_basic_permset(ace['perms']) == 'NOPERMS':
                    lockace_is_present = True
                elif ace['flags'].get('DIRECTORY_INHERIT') or ace['flags'].get('FILE_INHERIT'):
                    inheritable_is_present = True

                cleaned_acl.append(ace)

            if not inheritable_is_present:
                raise CallError('At least one inheritable ACL entry is required', errno.EINVAL)

            if options['canonicalize']:
                cleaned_acl = self.canonicalize_acl_order(cleaned_acl)

            if not lockace_is_present:
                locking_ace = {
                    'tag': 'EVERYONE',
                    'id': None,
                    'type': 'ALLOW',
                    'perms': self.__convert_to_adv_permset('NOPERMS'),
                    'flags': self.__convert_to_adv_flagset('INHERIT')
                }
                cleaned_acl.append(locking_ace)

            a = acl.ACL()
            a.__setstate__(cleaned_acl)
            a.apply(data['path'])

        if not options['recursive']:
            os.chown(data['path'], uid, gid)
            job.set_progress(100, 'Finished setting NFS4 ACL.')
            return

        job.set_progress(10, f'Recursively setting ACL on {data["path"]}.')
        self._winacl(data['path'], 'clone', uid, gid, options)
        job.set_progress(100, 'Finished setting NFS4 ACL.')

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
                        'aclentry',
                        Str('tag', enum=['owner@', 'group@', 'everyone@', 'USER', 'GROUP']),
                        Int('id', null=True),
                        Str('type', enum=['ALLOW', 'DENY']),
                        Dict(
                            'perms',
                            Bool('READ_DATA'),
                            Bool('WRITE_DATA'),
                            Bool('APPEND_DATA'),
                            Bool('READ_NAMED_ATTRS'),
                            Bool('WRITE_NAMED_ATTRS'),
                            Bool('EXECUTE'),
                            Bool('DELETE_CHILD'),
                            Bool('READ_ATTRIBUTES'),
                            Bool('WRITE_ATTRIBUTES'),
                            Bool('DELETE'),
                            Bool('READ_ACL'),
                            Bool('WRITE_ACL'),
                            Bool('WRITE_OWNER'),
                            Bool('SYNCHRONIZE'),
                            Str('BASIC', enum=['FULL_CONTROL', 'MODIFY', 'READ', 'TRAVERSE']),
                        ),
                        Dict(
                            'flags',
                            Bool('FILE_INHERIT'),
                            Bool('DIRECTORY_INHERIT'),
                            Bool('NO_PROPAGATE_INHERIT'),
                            Bool('INHERIT_ONLY'),
                            Bool('INHERITED'),
                            Str('BASIC', enum=['INHERIT', 'NOINHERIT']),
                        ),
                    ),
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
            Dict(
                'nfs41_flags',
                Bool('autoinherit', default=False),
                Bool('protected', default=False),
            ),
            Str('acltype', enum=[x.name for x in ACLType], default=ACLType.NFS4.name),
            Dict(
                'options',
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
                Bool('canonicalize', default=True)
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


class FileFollowTailEventSource(EventSource):

    """
    Retrieve last `no_of_lines` specified as an integer argument for a specific `path` and then
    any new lines as they are added. Specified argument has the format `path:no_of_lines` ( `/var/log/messages:3` ).

    `no_of_lines` is optional and if it is not specified it defaults to `3`.

    However `path` is required for this.
    """

    def run(self):
        if ':' in self.arg:
            path, lines = self.arg.rsplit(':', 1)
            lines = int(lines)
        else:
            path = self.arg
            lines = 3
        if not os.path.exists(path):
            # FIXME: Error?
            return

        bufsize = 8192
        fsize = os.stat(path).st_size
        if fsize < bufsize:
            bufsize = fsize
        i = 0
        with open(path) as f:
            data = []
            while True:
                i += 1
                if bufsize * i > fsize:
                    break
                f.seek(fsize - bufsize * i)
                data.extend(f.readlines())
                if len(data) >= lines or f.tell() == 0:
                    break

            self.send_event('ADDED', fields={'data': ''.join(data[-lines:])})
            f.seek(fsize)

            kqueue = select.kqueue()

            ev = [select.kevent(
                f.fileno(),
                filter=select.KQ_FILTER_VNODE,
                flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR,
                fflags=select.KQ_NOTE_DELETE | select.KQ_NOTE_EXTEND | select.KQ_NOTE_WRITE | select.KQ_NOTE_ATTRIB,
            )]
            kqueue.control(ev, 0, 0)

            while not self._cancel.is_set():
                events = kqueue.control([], 1, 1)
                if not events:
                    continue
                # TODO: handle other file operations other than just extend/write
                self.send_event('ADDED', fields={'data': f.read()})


def setup(middleware):
    middleware.register_event_source('filesystem.file_tail_follow', FileFollowTailEventSource)
