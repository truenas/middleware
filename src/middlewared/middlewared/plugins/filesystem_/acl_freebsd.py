from bsd import acl
import errno
import os
import subprocess
import stat as pystat

from middlewared.service import private, CallError, Service
from middlewared.plugins.smb import SMBBuiltin
from .acl_base import ACLBase, ACLDefault, ACLType


class FilesystemService(Service, ACLBase):

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

    def chown(self, job, data):
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

    def setperm(self, job, data):
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

        os.chown(data['path'], uid, gid)

        if not options['recursive']:
            job.set_progress(100, 'Finished setting permissions.')
            return

        action = 'clone' if mode else 'strip'
        job.set_progress(10, f'Recursively setting permissions on {data["path"]}.')
        self._winacl(data['path'], action, uid, gid, options)
        job.set_progress(100, 'Finished setting permissions.')

    async def default_acl_choices(self):
        acl_choices = []
        for x in ACLDefault:
            if x.value['visible']:
                acl_choices.append(x.name)

        return acl_choices

    async def get_default_acl(self, acl_type, share_type):
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

        gfacl = subprocess.run(['getfacl', '-q', '-n', path],
                               check=False, capture_output=True)
        if gfacl.returncode != 0:
            raise CallError(f"Failed to get POSIX1e ACL on path [{path}]: {gfacl.stderr.decode()}")

        # linux output adds extra line to output if it's an absolute path and extra newline at end.
        entries = gfacl.stdout.decode().splitlines()
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

    def getacl(self, path, simplified):
        if not os.path.exists(path):
            raise CallError('Path not found.', errno.ENOENT)

        if not os.pathconf(path, 64):
            return self.getacl_posix1e(path, simplified)

        return self.getacl_nfs4(path, simplified)

    @private
    def setacl_posix1e(self, job, data):
        raise CallError("POSIX1e brand ACLs not supported on the FreeBSD-based TrueNAS platform",
                        errno.EOPNOTSUPP)

    @private
    def setacl_nfs4(self, job, data):
        job.set_progress(0, 'Preparing to set acl.')
        options = data['options']
        dacl = data.get('dacl', [])

        if not os.pathconf(data['path'], 64):
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

    def setacl(self, job, data):
        acltype = ACLType[data['acltype']]
        if acltype == ACLType.NFS4:
            return self.setacl_nfs4(job, data)
        else:
            return self.setacl_posix1e(job, data)
