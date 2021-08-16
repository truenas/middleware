import enum
from middlewared.service import accepts, job, ServicePartBase
from middlewared.schema import Bool, Dict, Int, List, Str, UnixPerm
from middlewared.utils import osc
from middlewared.validators import Range


class ACLType(enum.Enum):
    NFS4 = (['tag', 'id', 'perms', 'flags', 'type'], ["owner@", "group@", "everyone@"])
    POSIX1E = (['default', 'tag', 'id', 'perms'], ["USER_OBJ", "GROUP_OBJ", "OTHER", "MASK"])
    DISABLED = ([], [])

    def _validate_id(self, id, special):
        if id is None or id < 0:
            return True if special else False

        return False if special else True

    def validate(self, theacl):
        errors = []
        ace_keys = self.value[0]
        special = self.value[1]

        if self != ACLType.NFS4 and theacl.get('nfs41flags'):
            errors.append(f"NFS41 ACL flags are not valid for ACLType [{self.name}]")

        for idx, entry in enumerate(theacl['dacl']):
            extra = set(entry.keys()) - set(ace_keys)
            missing = set(ace_keys) - set(entry.keys())
            if extra:
                errors.append(
                    (idx, f"ACL entry contains invalid extra key(s): {extra}", None)
                )
            if missing:
                errors.append(
                    (idx, f"ACL entry is missing required keys(s): {missing}", None)
                )

            if extra or missing:
                continue

            is_special = entry['tag'] in special
            if not self._validate_id(entry['id'], is_special):
                errors.append(
                    (idx, "ACL entry has invalid id for tag type.", "id")
                )

        return {"is_valid": len(errors) == 0, "errors": errors}

    def _is_inherited(self, ace):
        if ace['flags'].get("BASIC"):
            return False

        return ace['flags']['INHERITED']

    def canonicalize(self, theacl):
        """
        Order NFS4 ACEs according to MS guidelines:
        1) Deny ACEs that apply to the object itself (NOINHERIT)
        2) Allow ACEs that apply to the object itself (NOINHERIT)
        3) Deny ACEs that apply to a subobject of the object (INHERIT)
        4) Allow ACEs that apply to a subobject of the object (INHERIT)

        See http://docs.microsoft.com/en-us/windows/desktop/secauthz/order-of-aces-in-a-dacl
        Logic is simplified here because we do not determine depth from which ACLs are inherited.
        """
        if self == ACLType.POSIX1E:
            return

        out = []
        acl_groups = {
            "deny_noinherit": [],
            "deny_inherit": [],
            "allow_noinherit": [],
            "allow_inherit": [],
        }

        for ace in theacl:
            key = f'{ace["tag"].lower()}_{"inherit" if self.is_inherited(ace) else "noinherit"}'
            acl_groups[key].append(ace)

        for g in acl_groups.values():
            out.extend(g)

        return out


class ACLBase(ServicePartBase):

    @accepts(
        Dict(
            'filesystem_acl',
            Str('path', required=True),
            Int('uid', null=True, default=None, validators=[Range(min=-1, max=2147483647)]),
            Int('gid', null=True, default=None, validators=[Range(min=-1, max=2147483647)]),
            List(
                'dacl',
                items=[
                    Dict(
                        'nfs4_ace',
                        Str('tag', enum=['owner@', 'group@', 'everyone@', 'USER', 'GROUP']),
                        Int('id', null=True, validators=[Range(min=-1, max=2147483647)]),
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
                    ),
                    Dict(
                        'posix1e_ace',
                        Bool('default', default=False),
                        Str('tag', enum=['USER_OBJ', 'GROUP_OBJ', 'USER', 'GROUP', 'OTHER', 'MASK']),
                        Int('id', default=-1, validators=[Range(min=-1, max=2147483647)]),
                        Dict(
                            'perms',
                            Bool('READ', default=False),
                            Bool('WRITE', default=False),
                            Bool('EXECUTE', default=False),
                        ),
                        register=True
                    )
                ],
            ),
            Dict(
                'nfs41_flags',
                Bool('autoinherit', default=False),
                Bool('protected', default=False),
            ),
            Str('acltype', enum=[x.name for x in ACLType], null=True),
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

        Paths on clustered volumes may be specifed with the path prefix
        `CLUSTER:<volume name>`. For example, to list directories
        in the directory 'data' in the clustered volume `smb01`, the
        path should be specified as `CLUSTER:smb01/data`.

        `dacl` ACL entries. Formatting depends on the underlying `acltype`. NFS4ACL requires
        NFSv4 entries. POSIX1e requires POSIX1e entries.

        `uid` the desired UID of the file user. If set to None (the default), then user is not changed.

        `gid` the desired GID of the file group. If set to None (the default), then group is not changed.

        `recursive` apply the ACL recursively

        `traverse` traverse filestem boundaries (ZFS datasets)

        `strip` convert ACL to trivial. ACL is trivial if it can be expressed as a file mode without
        losing any access rules.

        `canonicalize` reorder ACL entries so that they are in concanical form as described
        in the Microsoft documentation MS-DTYP 2.4.5 (ACL). This only applies to NFSv4 ACLs.

        For case of NFSv4 ACLs  USER_OBJ, GROUP_OBJ, and EVERYONE with owner@, group@, everyone@ for
        consistency with getfacl and setfacl. If one of aforementioned special tags is used, 'id' must
        be set to None.

        An inheriting empty everyone@ ACE is appended to non-trivial ACLs in order to enforce Windows
        expectations regarding permissions inheritance. This entry is removed from NT ACL returned
        to SMB clients when 'ixnas' samba VFS module is enabled.
        """

    @accepts(
        Str('path'),
        Bool('simplified', default=True),
        Bool('resolve_ids', default=False),
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

    @accepts(
        Dict(
            'filesystem_ownership',
            Str('path', required=True),
            Int('uid', null=True, default=None, validators=[Range(min=-1, max=2147483647)]),
            Int('gid', null=True, default=None, validators=[Range(min=-1, max=2147483647)]),
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

    @accepts(
        Dict(
            'filesystem_permission',
            Str('path', required=True),
            UnixPerm('mode', null=True),
            Int('uid', null=True, default=None, validators=[Range(min=-1, max=2147483647)]),
            Int('gid', null=True, default=None, validators=[Range(min=-1, max=2147483647)]),
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
        Set unix permissions on given `path`.

        Paths on clustered volumes may be specifed with the path prefix
        `CLUSTER:<volume name>`. For example, to list directories
        in the directory 'data' in the clustered volume `smb01`, the
        path should be specified as `CLUSTER:smb01/data`.

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

    @accepts(Str('path', required=False, default=''))
    async def default_acl_choices(self, path):
        """
        `DEPRECATED`
        Returns list of names of ACL templates. Wrapper around
        filesystem.acltemplate.query.
        """

    @accepts(
        Str('acl_type', default='POSIX_OPEN'),
        Str('share_type', default='NONE', enum=['NONE', 'SMB', 'NFS']),
    )
    async def get_default_acl(self, acl_type, share_type):
        """
        `DEPRECATED`
        Returns a default ACL depending on the usage specified by `acl_type`.
        If an admin group is defined, then an entry granting it full control will
        be placed at the top of the ACL. Optionally may pass `share_type` to argument
        to get share-specific template ACL.
        """
