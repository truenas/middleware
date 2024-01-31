import errno
import json
import os
import subprocess
import stat as pystat
from pathlib import Path

from middlewared.plugins.chart_releases_linux.utils import is_ix_volume_path
from middlewared.schema import Bool, Dict, Int, List, Str, Ref, UnixPerm, OROperator
from middlewared.service import accepts, private, returns, job, CallError, ValidationErrors, Service
from middlewared.utils.path import FSLocation, path_location
from middlewared.validators import Range
from .utils import ACLType


class FilesystemService(Service):

    class Config:
        cli_private = True

    def __acltool(self, path, action, uid, gid, options):

        flags = "-r"
        flags += "x" if options.get('traverse') else ""
        flags += "C" if options.get('do_chmod') else ""
        flags += "P" if options.get('posixacl') else ""

        acltool = subprocess.run([
            '/usr/bin/nfs4xdr_winacl',
            '-a', action,
            '-O', str(uid), '-G', str(gid),
            flags,
            '-c', path,
            '-p', path], check=False, capture_output=True
        )
        if acltool.returncode != 0:
            raise CallError(f"acltool [{action}] on path {path} failed with error: [{acltool.stderr.decode().strip()}]")

    def _common_perm_path_validate(self, schema, data, verrors):
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

        if any(st['realpath'].startswith(prefix) for prefix in ('/home/admin/.ssh', '/root/.ssh')):
            return loc

        if not st['realpath'].startswith('/mnt/'):
            verrors.add(
                f'{schema}.path',
                "Changes to permissions on paths that are not beneath "
                f"the directory /mnt are not permitted: {path}"
            )

        elif len(Path(st['realpath']).resolve().parents) == 2:
            verrors.add(
                f'{schema}.path',
                f'The specified path is a ZFS pool mountpoint "({path})" '
            )

        elif self.middleware.call_sync('pool.dataset.path_in_locked_datasets', st['realpath']):
            verrors.add(
                f'{schema}.path',
                'Path component for is currently encrypted and locked'
            )

        apps_dataset = self.middleware.call_sync('kubernetes.config')['dataset']
        if apps_dataset and st['realpath'].startswith(f'/mnt/{apps_dataset}')\
                and not is_ix_volume_path(st['realpath'], apps_dataset):
            verrors.add(
                f'{schema}.path',
                f'Changes to permissions of ix-applications dataset are not permitted: {path}.'
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

        try:
            os.getxattr(path, "system.posix_acl_access")
            return ACLType.POSIX1E.name

        except OSError as e:
            if e.errno == errno.ENODATA:
                return ACLType.POSIX1E.name

            if e.errno != errno.EOPNOTSUPP:
                raise

        try:
            os.getxattr(path, "system.nfs4_acl_xdr")
            return ACLType.NFS4.name
        except OSError as e:
            if e.errno == errno.EOPNOTSUPP:
                return ACLType.DISABLED.name

            raise

    @accepts(
        Dict(
            'filesystem_ownership',
            Str('path', required=True),
            Int('uid', null=True, default=None, validators=[Range(min_=-1, max_=2147483647)]),
            Int('gid', null=True, default=None, validators=[Range(min_=-1, max_=2147483647)]),
            Dict(
                'options',
                Bool('recursive', default=False),
                Bool('traverse', default=False)
            )
        ),
        roles=['FILESYSTEM_ATTRS_WRITE']
    )
    @returns()
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
        verrors = ValidationErrors()

        uid = -1 if data['uid'] is None else data.get('uid', -1)
        gid = -1 if data['gid'] is None else data.get('gid', -1)
        options = data['options']

        if uid == -1 and gid == -1:
            verrors.add("filesystem.chown.uid",
                        "Please specify either user or group to change.")

        loc = self._common_perm_path_validate("filesystem.chown", data, verrors)
        verrors.check()

        if not options['recursive']:
            job.set_progress(100, 'Finished changing owner.')
            os.chown(data['path'], uid, gid)
            return

        job.set_progress(10, f'Recursively changing owner of {data["path"]}.')
        options['posixacl'] = True
        self.__acltool(data['path'], 'chown', uid, gid, options)
        job.set_progress(100, 'Finished changing owner.')

    @private
    def _strip_acl_nfs4(self, path):
        stripacl = subprocess.run(
            ['nfs4xdr_setfacl', '-b', path],
            capture_output=True,
            check=False
        )
        if stripacl.returncode != 0:
            raise CallError("Failed to strip ACL on path: %s",
                            stripacl.stderr.decode())

        return

    @private
    def _strip_acl_posix1e(self, path):
        posix_xattrs = ['system.posix_acl_access', 'system.posix_acl_default']
        for xat in os.listxattr(path):
            if xat not in posix_xattrs:
                continue

            os.removexattr(path, xat)

    @accepts(
        Dict(
            'filesystem_permission',
            Str('path', required=True),
            UnixPerm('mode', null=True),
            Int('uid', null=True, default=None, validators=[Range(min_=-1, max_=2147483647)]),
            Int('gid', null=True, default=None, validators=[Range(min_=-1, max_=2147483647)]),
            Dict(
                'options',
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
            )
        ),
        roles=['FILESYSTEM_ATTRS_WRITE']
    )
    @returns()
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

        loc = self._common_perm_path_validate("filesystem.setperm", data, verrors)

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

        if is_nfs4acl:
            self._strip_acl_nfs4(data['path'])
        else:
            self._strip_acl_posix1e(data['path'])

        if mode:
            os.chmod(data['path'], mode)

        os.chown(data['path'], uid, gid)

        if not options['recursive']:
            job.set_progress(100, 'Finished setting permissions.')
            return

        action = 'clone' if mode else 'strip'
        job.set_progress(10, f'Recursively setting permissions on {data["path"]}.')
        options['posixacl'] = not is_nfs4acl
        options['do_chmod'] = True
        self.__acltool(data['path'], action, uid, gid, options)
        job.set_progress(100, 'Finished setting permissions.')

    @accepts(Str('path', required=False, default=''))
    @returns(List('acl_choices', items=[Str("choice")]))
    async def default_acl_choices(self, path):
        """
        `DEPRECATED`
        Returns list of names of ACL templates. Wrapper around
        filesystem.acltemplate.query.
        """
        acl_templates = await self.middleware.call('filesystem.acltemplate.by_path', {"path": path})
        return [x['name'] for x in acl_templates]

    @accepts(
        Str('acl_type', default='POSIX_OPEN'),
        Str('share_type', default='NONE', enum=['NONE', 'SMB', 'NFS']),
    )
    @returns(OROperator(Ref('nfs4_acl'), Ref('posix1e_acl'), name='acl'))
    async def get_default_acl(self, acl_type, share_type):
        """
        `DEPRECATED`
        Returns a default ACL depending on the usage specified by `acl_type`.
        If an admin group is defined, then an entry granting it full control will
        be placed at the top of the ACL. Optionally may pass `share_type` to argument
        to get share-specific template ACL.
        """
        filters = [("name", "=", acl_type)]
        options = {"ensure_builtins": share_type == "SMB"}
        return (await self.middleware.call("filesystem.acltemplate.by_path", {
            "query-filters": filters,
            "format-options": options
        }))[0]['acl']

    @private
    def getacl_nfs4(self, path, simplified, resolve_ids):
        flags = "-jn"

        if not simplified:
            flags += "v"

        getacl = subprocess.run(
            ['nfs4xdr_getfacl', flags, path],
            capture_output=True,
            check=False
        )
        if getacl.returncode != 0:
            raise CallError("Failed to get ACL for path [%s]: %s",
                            path, getacl.stderr.decode())

        output = json.loads(getacl.stdout.decode())
        for ace in output['acl']:
            if resolve_ids and ace['id'] != -1:
                ace['who'] = self.middleware.call_sync(
                    'idmap.id_to_name', ace['id'], ace['tag']
                )
            elif resolve_ids and ace['tag'] == 'group@':
                ace['who'] = self.middleware.call_sync(
                    'idmap.id_to_name', output['gid'], 'GROUP'
                )
            elif resolve_ids and ace['tag'] == 'owner@':
                ace['who'] = self.middleware.call_sync(
                    'idmap.id_to_name', output['uid'], 'USER'
                )
            elif resolve_ids:
                ace['who'] = None

            ace['flags'].pop('SUCCESSFUL_ACCESS', None)
            ace['flags'].pop('FAILED_ACCESS', None)

        na41flags = output.pop('nfs41_flags')
        output['nfs41_flags'] = {
            "protected": na41flags['PROTECTED'],
            "defaulted": na41flags['DEFAULTED'],
            "autoinherit": na41flags['AUTOINHERIT']
        }
        output['acltype'] = 'NFS4'
        return output

    @private
    def getacl_posix1e(self, path, simplified, resolve_ids):
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

            entry = entry.split("\t")[0]
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

            tag, id_, perms = entry.rsplit(":", 2)
            ace['perms'].update({
                "READ": perms[0].casefold() == "r",
                "WRITE": perms[1].casefold() == "w",
                "EXECUTE": perms[2].casefold() == "x",
            })
            if tag.startswith('default'):
                ace['default'] = True
                tag = tag[8:]

            ace['tag'] = tag.upper()
            if id_.isdigit():
                ace['id'] = int(id_)
                if resolve_ids:
                    ace['who'] = self.middleware.call_sync(
                        'idmap.id_to_name', ace['id'], ace['tag']
                    )

            elif ace['tag'] not in ['OTHER', 'MASK']:
                if resolve_ids:
                    to_check = st.st_gid if ace['tag'] == "GROUP" else st.st_uid
                    ace['who'] = self.middleware.call_sync(
                        'idmap.id_to_name', to_check, ace['tag']
                    )

                ace['tag'] += '_OBJ'

            elif resolve_ids:
                ace['who'] = None

            ret['acl'].append(ace)

        ret['trivial'] = (len(ret['acl']) == 3)
        ret['path'] = path
        return ret

    @private
    def getacl_disabled(self, path):
        st = os.stat(path)
        return {
            'uid': st.st_uid,
            'gid': st.st_gid,
            'acl': [],
            'acltype': ACLType.DISABLED.name,
            'trivial': True,
        }

    @accepts(
        Str('path'),
        Bool('simplified', default=True),
        Bool('resolve_ids', default=False),
        roles=['FILESYSTEM_ATTRS_READ']
    )
    @returns(Dict(
        'truenas_acl',
        Str('path'),
        Bool('trivial'),
        Str('acltype', enum=[x.name for x in ACLType], null=True),
        OROperator(
            Ref('nfs4_acl'),
            Ref('posix1e_acl'),
            name='acl'
        )
    ))
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

        path_acltype = self.path_get_acltype(path)
        acltype = ACLType[path_acltype]

        if acltype == ACLType.NFS4:
            ret = self.getacl_nfs4(path, simplified, resolve_ids)
        elif acltype == ACLType.POSIX1E:
            ret = self.getacl_posix1e(path, simplified, resolve_ids)
        else:
            ret = self.getacl_disabled(path)

        return ret

    @private
    def setacl_nfs4_internal(self, path, acl, do_canon, verrors):
        payload = {
            'acl': ACLType.NFS4.canonicalize(acl) if do_canon else acl,
        }
        json_payload = json.dumps(payload)
        setacl = subprocess.run(
            ['nfs4xdr_setfacl', '-j', json_payload, path],
            capture_output=True,
            check=False
        )
        """
        nfs4xr_setacl with JSON input will return validation
        errors on exit with EX_DATAERR (65).
        """
        if setacl.returncode == 65:
            err = setacl.stderr.decode()
            json_verrors = json.loads(err.split(None, 1)[1])
            for entry in json_verrors:
                for schema, err in entry.items():
                    verrors.add(f'filesystem_acl.{schema.replace("acl", "dacl")}', err)

            verrors.check()

        elif setacl.returncode != 0:
            raise CallError(setacl.stderr.decode())

    @private
    def setacl_nfs4(self, job, data):
        job.set_progress(0, 'Preparing to set acl.')
        verrors = ValidationErrors()
        options = data.get('options', {})
        recursive = options.get('recursive', False)
        do_strip = options.get('stripacl', False)
        do_canon = options.get('canonicalize', False)

        path = data.get('path', '')
        uid = -1 if data['uid'] is None else data.get('uid', -1)
        gid = -1 if data['gid'] is None else data.get('gid', -1)

        aclcheck = ACLType.NFS4.validate(data)
        if not aclcheck['is_valid']:
            for err in aclcheck['errors']:
                if err[2]:
                    v = f'filesystem_acl.dacl.{err[0]}.{err[2]}'
                else:
                    v = f'filesystem_acl.dacl.{err[0]}'

                verrors.add(v, err[1])

        current_acl = self.getacl(path)
        if current_acl['acltype'] != ACLType.NFS4.name:
            verrors.add(
                'filesystem_acl.acltype',
                f'ACL type mismatch. On-disk format is [{current_acl["acltype"]}], '
                f'but received [{data.get("acltype")}].'
            )

        verrors.check()

        if do_strip:
            self._strip_acl_nfs4(path)

        else:
            uid_to_check = current_acl['uid'] if uid == -1 else uid
            gid_to_check = current_acl['gid'] if gid == -1 else gid

            self.middleware.call_sync(
                'filesystem.check_acl_execute',
                path, data['dacl'], uid_to_check, gid_to_check, True
            )

            self.setacl_nfs4_internal(path, data['dacl'], do_canon, verrors)

        if not recursive:
            os.chown(path, uid, gid)
            job.set_progress(100, 'Finished setting NFSv4 ACL.')
            return

        self.__acltool(path, 'clone' if not do_strip else 'strip',
                       uid, gid, options)

        job.set_progress(100, 'Finished setting NFSv4 ACL.')

    @private
    def gen_aclstring_posix1e(self, dacl, recursive, verrors):
        """
        This method iterates through provided POSIX1e ACL and
        performs addtional validation before returning the ACL
        string formatted for the setfacl command. In case
        of ValidationError, None is returned.
        """
        has_tag = {
            "USER_OBJ": False,
            "GROUP_OBJ": False,
            "OTHER": False,
            "MASK": False,
            "DEF_USER_OBJ": False,
            "DEF_GROUP_OBJ": False,
            "DEF_OTHER": False,
            "DEF_MASK": False,
        }
        required_entries = ["USER_OBJ", "GROUP_OBJ", "OTHER"]
        has_named = False
        has_def_named = False
        has_default = False
        aclstring = ""

        for idx, ace in enumerate(dacl):
            if idx != 0:
                aclstring += ","

            if ace['id'] == -1:
                ace['id'] = ''

            who = "DEF_" if ace['default'] else ""
            who += ace['tag']
            duplicate_who = has_tag.get(who)

            if duplicate_who is True:
                verrors.add(
                    'filesystem_acl.dacl.{idx}',
                    f'More than one {"default" if ace["default"] else ""} '
                    f'{ace["tag"]} entry is not permitted'
                )

            elif duplicate_who is False:
                has_tag[who] = True

            if ace['tag'] in ["USER", "GROUP"]:
                if ace['default']:
                    has_def_named = True
                else:
                    has_named = True

            ace['tag'] = ace['tag'].rstrip('_OBJ').lower()

            if ace['default']:
                has_default = True
                aclstring += "default:"

            aclstring += f"{ace['tag']}:{ace['id']}:"
            aclstring += 'r' if ace['perms']['READ'] else '-'
            aclstring += 'w' if ace['perms']['WRITE'] else '-'
            aclstring += 'x' if ace['perms']['EXECUTE'] else '-'

        if has_named and not has_tag['MASK']:
            verrors.add(
                'filesystem_acl.dacl',
                'Named (user or group) POSIX ACL entries '
                'require a mask entry to be present in the ACL.'
            )

        elif has_def_named and not has_tag['DEF_MASK']:
            verrors.add(
                'filesystem_acl.dacl',
                'Named default (user or group) POSIX ACL entries '
                'require a default mask entry to be present in the ACL.'
            )

        if recursive and not has_default:
            verrors.add(
                'filesystem_acl.dacl',
                'Default ACL entries are required in order to apply '
                'ACL recursively.'
            )

        for entry in required_entries:
            if not has_tag[entry]:
                verrors.add(
                    'filesystem_acl.dacl',
                    f'Presence of [{entry}] entry is required.'
                )

            if has_default and not has_tag[f"DEF_{entry}"]:
                verrors.add(
                    'filesystem_acl.dacl',
                    f'Presence of default [{entry}] entry is required.'
                )

        return aclstring

    @private
    def setacl_posix1e(self, job, data):
        job.set_progress(0, 'Preparing to set acl.')
        verrors = ValidationErrors()
        options = data['options']
        recursive = options.get('recursive', False)
        do_strip = options.get('stripacl', False)
        dacl = data.get('dacl', [])
        path = data['path']
        uid = -1 if data['uid'] is None else data.get('uid', -1)
        gid = -1 if data['gid'] is None else data.get('gid', -1)

        aclcheck = ACLType.POSIX1E.validate(data)
        if not aclcheck['is_valid']:
            for err in aclcheck['errors']:
                if err[2]:
                    v = f'filesystem_acl.dacl.{err[0]}.{err[2]}'
                else:
                    v = f'filesystem_acl.dacl.{err[0]}'

                verrors.add(v, err[1])

        current_acl = self.getacl(path)
        if current_acl['acltype'] != ACLType.POSIX1E.name:
            verrors.add(
                'filesystem_acl.acltype',
                f'ACL type mismatch. On-disk format is [{current_acl["acltype"]}], '
                f'but received [{data.get("acltype")}].'
            )

        if do_strip and dacl:
            verrors.add(
                'filesystem_acl.dacl',
                'Simulatenously setting and removing ACL from path is invalid.'
            )

        if not do_strip:
            try:
                # check execute on parent paths
                uid_to_check = current_acl['uid'] if uid == -1 else uid
                gid_to_check = current_acl['gid'] if gid == -1 else gid

                self.middleware.call_sync(
                    'filesystem.check_acl_execute',
                    path, dacl, uid_to_check, gid_to_check, True
                )
            except CallError as e:
                if e.errno != errno.EPERM:
                    raise

                verrors.add(
                    'filesystem_acl.path',
                    e.errmsg
                )

            aclstring = self.gen_aclstring_posix1e(dacl, recursive, verrors)

        verrors.check()

        self._strip_acl_posix1e(path)

        job.set_progress(50, 'Setting POSIX1e ACL.')

        if not do_strip:
            setacl = subprocess.run(['setfacl', '-m', aclstring, path],
                                    check=False, capture_output=True)
            if setacl.returncode != 0:
                raise CallError(f'Failed to set ACL [{aclstring}] on path [{path}]: '
                                f'{setacl.stderr.decode()}')

        if not recursive:
            os.chown(path, uid, gid)
            job.set_progress(100, 'Finished setting POSIX1e ACL.')
            return

        options['posixacl'] = True
        self.__acltool(data['path'],
                       'clone' if not do_strip else 'strip',
                       uid, gid, options)

        job.set_progress(100, 'Finished setting POSIX1e ACL.')

    @accepts(
        Dict(
            'filesystem_acl',
            Str('path', required=True),
            Int('uid', null=True, default=None, validators=[Range(min_=-1, max_=2147483647)]),
            Int('gid', null=True, default=None, validators=[Range(min_=-1, max_=2147483647)]),
            OROperator(
                List(
                    'nfs4_acl',
                    items=[Dict(
                        'nfs4_ace',
                        Str('tag', enum=['owner@', 'group@', 'everyone@', 'USER', 'GROUP']),
                        Int('id', null=True, validators=[Range(min_=-1, max_=2147483647)]),
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
                        register=True
                    )],
                    register=True
                ),
                List(
                    'posix1e_acl',
                    items=[Dict(
                        'posix1e_ace',
                        Bool('default', default=False),
                        Str('tag', enum=['USER_OBJ', 'GROUP_OBJ', 'USER', 'GROUP', 'OTHER', 'MASK']),
                        Int('id', default=-1, validators=[Range(min_=-1, max_=2147483647)]),
                        Dict(
                            'perms',
                            Bool('READ', default=False),
                            Bool('WRITE', default=False),
                            Bool('EXECUTE', default=False),
                        ),
                        register=True
                    )],
                    register=True
                ),
                name='dacl',
            ),
            Dict(
                'nfs41_flags',
                Bool('autoinherit', default=False),
                Bool('protected', default=False),
                Bool('defaulted', default=False),
            ),
            Str('acltype', enum=[x.name for x in ACLType], null=True),
            Dict(
                'options',
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
                Bool('canonicalize', default=True)
            )
        ), roles=['FILESYSTEM_ATTRS_WRITE']
    )
    @returns()
    @job(lock="perm_change")
    def setacl(self, job, data):
        verrors = ValidationErrors()
        data['loc'] = self._common_perm_path_validate("filesystem.setacl", data, verrors)
        verrors.check()

        if 'acltype' in data:
            acltype = ACLType[data['acltype']]
        else:
            path_acltype = self.path_get_acltype(data['path'])
            acltype = ACLType[path_acltype]

        if acltype == ACLType.NFS4:
            return self.setacl_nfs4(job, data)
        elif acltype == ACLType.POSIX1E:
            return self.setacl_posix1e(job, data)
        else:
            raise CallError(f"{data['path']}: ACLs disabled on path.", errno.EOPNOTSUPP)

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

    @private
    @accepts(Dict(
        'add_to_acl',
        Str('path', required=True),
        List('entries', required=True, items=[Dict(
            'simplified_acl_entry',
            Str('id_type', enum=['USER', 'GROUP'], required=True),
            Int('id', required=True),
            Str('access', enum=['READ', 'MODIFY', 'FULL_CONTROL'], required=True)
        )]),
        Dict(
            'options',
            Bool('force', default=False),
        )
    ), roles=['FILESYSTEM_ATTRS_WRITE'])
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

        if next(Path(data['path']).iterdir(), None) and not data['options']['force']:
            raise CallError(
                f'{data["path"]}: path contains existing data '
                'and `force` was not specified', errno.EPERM
            )

        data['path'] = init_path
        current_acl = self.getacl(data['path'])
        acltype = ACLType[current_acl['acltype']]

        if acltype == ACLType.NFS4:
            changed = self.add_to_acl_nfs4(current_acl['acl'], data['entries'])
        elif acltype == ACLType.POSIX1E:
            changed = self.add_to_acl_posix(current_acl['acl'], data['entries'])
        else:
            raise CallError(f"{data['path']}: ACLs disabled on path.", errno.EOPNOTSUPP)

        if not changed:
            job.set_progress(100, 'ACL already contains all requested entries.')
            return

        setacl_job = self.middleware.call_sync('filesystem.setacl', {
            'path': data['path'],
            'dacl': current_acl['acl'],
            'acltype': current_acl['acltype'],
            'options': {'recursive': True}
        })

        return job.wrap_sync(setacl_job)

    @private
    @accepts(Dict(
        'calculate_inherited_acl',
        Str('path', required=True),
        Dict(
            'options',
            Bool('directory', default=True)
        )
    ))
    def get_inherited_acl(self, data):
        """
        Generate an inherited ACL based on given `path`
        Supports `directory` `option` that allows specifying whether the generated
        ACL is for a file or a directory.
        """
        init_path = data['path']
        verrors = ValidationErrors()
        self._common_perm_path_validate('filesystem.add_to_acl', data, verrors)
        verrors.check()

        current_acl = self.getacl(data['path'], False)
        acltype = ACLType[current_acl['acltype']]

        return acltype.calculate_inherited(current_acl, data['options']['directory'])
