import errno
import os
import subprocess
import stat as pystat

from middlewared.service import private, CallError, Service
from middlewared.plugins.smb import SMBBuiltin
from .acl_base import ACLBase, ACLDefault, ACLType


class FilesystemService(Service, ACLBase):

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

    async def default_acl_choices(self):
        acl_choices = []
        for x in ACLDefault:
            if x.value['visible']:
                acl_choices.append(x.name)

        return acl_choices

    async def get_default_acl(self, acl_type, share_type):
        acl = []
        admin_group = (await self.middleware.call('smb.config'))['admin_group']
        if admin_group:
            acl.append({
                'default': True,
                'tag': 'GROUP',
                'id': (await self.middleware.call('dscache.get_uncached_group', admin_group))['gr_gid'],
                'perms': {'READ': True, 'WRITE': True, 'EXECUTE': True},
            })
        if share_type == 'SMB':
            acl.append({
                'default': True,
                'tag': 'GROUP',
                'id': int(SMBBuiltin['USERS'].value[1][9:]),
                'perms': {'READ': True, 'WRITE': True, 'EXECUTE': True},
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

        gfacl = subprocess.run(['getfacl', '-c', '-n', path],
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
            elif ace['tag'] != 'OTHER':
                ace['tag'] += '_OBJ'

            ret['acl'].append(ace)

        return ret

    def getacl(self, path, simplified):
        if not os.path.exists(path):
            raise CallError('Path not found.', errno.ENOENT)

        return self.getacl_posix1e(path, simplified)

    @private
    def setacl_nfs4(self, job, data):
        raise CallError('NFSv4 ACLs are not yet implemented.', errno.ENOTSUP)

    @private
    def setacl_posix1e(self, job, data):
        job.set_progress(0, 'Preparing to set acl.')

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

    def setacl(self, job, data):
        acltype = ACLType[data['acltype']]
        if acltype == ACLType.NFS4:
            return self.setacl_nfs4(job, data)
        else:
            return self.setacl_posix1e(job, data)
