from middlewared.service import CallError, CRUDService, ValidationErrors
from middlewared.service import accepts, private, returns
from middlewared.schema import Bool, Dict, Int, List, Str, Ref, Patch, OROperator
from middlewared.plugins.smb import SMBBuiltin
from .acl_base import ACLType

import middlewared.sqlalchemy as sa
import errno
import os


class ACLTempateModel(sa.Model):
    __tablename__ = 'filesystem_acltemplate'

    id = sa.Column(sa.Integer(), primary_key=True)
    acltemplate_name = sa.Column(sa.String(120), unique=True)
    acltemplate_acltype = sa.Column(sa.String(255), nullable=True)
    acltemplate_acl = sa.Column(sa.JSON(type=list))
    acltemplate_builtin = sa.Column(sa.Boolean())


class ACLTemplateService(CRUDService):

    class Config:
        cli_namespace = 'filesystem.acltemplate'
        datastore = 'filesystem.acltemplate'
        datastore_prefix = 'acltemplate_'
        namespace = 'filesystem.acltemplate'

    @private
    async def validate_acl(self, data, schema, verrors):
        acltype = ACLType[data['acltype']]
        aclcheck = acltype.validate(data['acl'])
        if not aclcheck['is_valid']:
            for err in aclcheck['errors']:
                if err[2]:
                    v = f'{schema}.{err[0]}.{err[2]}'
                else:
                    v = f'{schema}.{err[0]}'

                verrors.add(v, err[1])

        if acltype is ACLType.POSIX1E:
            await self.middleware.call(
                "filesystem.gen_aclstring_posix1e",
                data["acl"], False, verrors
            )

        for idx, ace in enumerate(data['acl']):
            if ace['id'] is None:
                verrors.add(f'{schema}.{idx}.id', 'null id is not permitted.')

    @accepts(Dict(
        "acltemplate_create",
        Str("name", required=True),
        Str("acltype", required=True, enum=["NFS4", "POSIX1E"]),
        OROperator(Ref('nfs4_acl'), Ref('posix1e_acl'), name='acl', requried=True),
        register=True
    ))
    @returns(Ref('acltemplate_create'))
    async def create(self, data):
        verrors = ValidationErrors()
        if len(data['acl']) == 0:
            verrors.add(
                "filesystem_acltemplate_create.acl",
                "At least one ACL entry must be specified."
            )
        await self.validate_acl(data, "filesystem_acltemplate_create.acl", verrors)
        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        return await self._get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'acltemplate_create',
            'acltemplate_update',
            ('attr', {'update': True})
        )
    )
    @returns(Ref('acltemplate_create'))
    async def do_update(self, id, data):
        old = await self.get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        if old['builtin']:
            verrors.add("filesystem_acltemplate_update.builtin",
                        "built-in ACL templates may not be changed")

        if new['name'] != old['name']:
            name_exists = bool(await self.query(['name', '=', new['name']]))
            if name_exists:
                verrors.add("filesystem_acltemplate_update.name",
                            f"{data['name']}: name is not unique")

        if len(data['acl']) == 0:
            verrors.add(
                "filesystem_acltemplate_update.acl",
                "At least one ACL entry must be specified."
            )
        await self.validate_acl(data, "filesystem_acltemplate_update.acl", verrors)
        verrors.check()

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        return await self.get_instance(id)

    @accepts(Int('id'))
    @returns()
    async def do_delete(self, id):
        entry = await self.get_instance(id)
        if entry['builtin']:
            raise CallError("Deletion of builtin templates is not permitted",
                            errno.EPERM)

        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id
        )

    @private
    async def append_builtins(self, data):
        """
        This method ensures that ACL grants some minimum level of permissions
        to our builtin users or builtin admins accounts.
        """
        bu_id = int(SMBBuiltin.USERS.value[1][9:])
        ba_id = int(SMBBuiltin.USERS.value[1][9:])
        has_builtins = any(filter(lambda x: x["id"] in [bu_id, ba_id], data['acl']))
        if has_builtins:
            return

        if data['acltype'] == ACLType.NFS4.name:
            data['acl'].extend([
                {"tag": "GROUP", "id": bu_id, "perms": {"BASIC": "MODIFY"}, "flags": {"BASIC": "INHERIT"}, "type": "ALLOW"},
                {"tag": "GROUP", "id": ba_id, "perms": {"BASIC": "FULL_CONTROL"}, "flags": {"BASIC": "INHERIT"}, "type": "ALLOW},
            ])
            return

        has_default_mask = any(filter(lambda x: x["tag"] == "MASK" and x["default"], data['acl']))
        has_access_mask = any(filter(lambda x: x["tag"] == "MASK" and x["default"], data['acl']))
        all_perms = {"READ": True, "WRITE": True, "EXECUTE": True}
        data['acl'].extend([
            {"tag": "GROUP", "id": bu_id, "perms": all_perms, "default": False},
            {"tag": "GROUP", "id": bu_id, "perms": all_perms, "default": True},
            {"tag": "GROUP", "id": ba_id, "perms": all_perms, "default": False},
            {"tag": "GROUP", "id": ba_id, "perms": all_perms, "default": True},
        ])

        if not has_default_mask:
            data['acl'].append({"tag": "MASK", "id": -1, "perms": all_perms, "default": False})

        if not has_access_mask:
            data['acl'].append({"tag": "MASK", "id": -1, "perms": all_perms, "default": True})

        return

    @private
    async def resolve_names(self, uid, gid, data):
        for ace in data['acl']:
            if ace['id'] != -1:
                ace['who'] = await self.middleware.call(
                    'idmap.id_to_name', ace['id'], ace['tag']
                )
            elif ace['tag'] in ('group@', 'GROUP_OBJ'):
                ace['who'] = await self.middleware.call(
                    'idmap.id_to_name', gid, 'GROUP'
                )
            elif ace['tag'] in ('owner@', 'USER_OBJ'):
                ace['who'] = await self.middleware.call(
                    'idmap.id_to_name', uid, 'USER'
                )
            else:
                ace['who'] = None

        return

    @accepts(Dict(
        "acltemplate_by_path",
        Str("path", default=""),
        Ref('query-filters'),
        Ref('query-options'),
        Dict(
            "format-options",
            Bool("canonicalize", default=False),
            Bool("ensure_builtins", default=False),
            Bool("resolve_names", default=False),
        )
    ))
    @returns(List(
        'templates',
        items=[Patch('acltemplate_create', 'acltemplate', ('add', {'name': 'id', 'type': 'int'}))]
    ))
    async def by_path(self, data):
        """
        Retrieve list of available ACL templates for a given `path`.

        Supports `query-filters` and `query-options`.
        `format-options` gives additional options to alter the results of
        the template query:

        `canonicalize` - place ACL entries for NFSv4 ACLs in Microsoft canonical order.
        `ensure_builtins` - ensure all results contain entries for `builtin_users` and `builtin_administrators`
        groups.
        `resolve_names` - convert ids in ACL entries into names.
        """
        verrors = ValidationErrors()
        filters = data.get('query-filters')
        if data['path']:
            path = await self.middleware.call(
                "filesystem.resolve_cluster_path", data['path']
            )
            acltype = await self.middleware.call(
                'filesystem.path_get_acltype', data['path']
            )
            if acltype == ACLType.DISABLED.name:
                return []

            if acltype == ACLType.POSIX1E.name and data['format-options']['canonicalize']:
                verrors.add(
                    "filesystem.acltemplate_by_path.format-options.canonicalize",
                    "POSIX1E ACLs may not be sorted into Windows canonical order."
                )
            filters.append(("acltype", "=", acltype))

        if not data['path'] and data['format-options']['resolve_names']:
            verrors.add(
                "filesystem.acltemplate_by_path.format-options.canonicalize",
                "ACL entry ids may not be resolved into names unless path is provided."
            )

        verrors.check()

        templates = await self.query(filters, data['query-options'])
        for t in templates:
            if data['format-options']['ensure_builtins']:
                await self.append_builtins(t)

            if data['format-options']['resolve_names']:
                st = await self.middleware.run_in_thread(os.stat(path))
                await self.resolve_names(st.st_uid, st.st_gid, t)

            if data['format-options']['canonicalize'] and t['acltype'] == ACLType.NFS4.name:
                canonicalized = ACLType[t['acltype']].canonicalize(t['acl'])
                t['acl'] = canonicalized

        return templates
