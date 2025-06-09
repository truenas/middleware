from middlewared.api import api_method
from middlewared.api.current import (
    AclTemplateEntry,
    AclTemplateByPathArgs, AclTemplateByPathResult,
    AclTemplateCreateArgs, AclTemplateCreateResult,
    AclTemplateUpdateArgs, AclTemplateUpdateResult,
    AclTemplateDeleteArgs, AclTemplateDeleteResult,
)
from middlewared.service import CallError, CRUDService, ValidationErrors
from middlewared.service import private
from middlewared.plugins.smb_.constants import SMBBuiltin
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    FS_ACL_Type,
    NFS4_SPECIAL_ENTRIES,
    POSIX_SPECIAL_ENTRIES
)
from .utils import canonicalize_nfs4_acl, gen_aclstring_posix1e

import middlewared.sqlalchemy as sa
import errno
import os
import copy


class ACLTempateModel(sa.Model):
    __tablename__ = 'filesystem_acltemplate'

    id = sa.Column(sa.Integer(), primary_key=True)
    acltemplate_name = sa.Column(sa.String(120), unique=True)
    acltemplate_comment = sa.Column(sa.Text())
    acltemplate_acltype = sa.Column(sa.String(255))
    acltemplate_acl = sa.Column(sa.JSON(list))
    acltemplate_builtin = sa.Column(sa.Boolean())


class ACLTemplateService(CRUDService):

    class Config:
        datastore = 'filesystem.acltemplate'
        datastore_prefix = 'acltemplate_'
        datastore_extend = 'filesystem.acltemplate.extend'
        namespace = 'filesystem.acltemplate'
        cli_private = True
        entry = AclTemplateEntry
        role_prefix = 'FILESYSTEM_ATTRS'

    @private
    async def extend(self, data):
        # Normalize entries for raw query. API consumer can request to
        # resolve IDs in filesystem.acltemplate.by_path
        for ace in data['acl']:
            ace['who'] = None

        return data

    @private
    async def validate_acl(self, data, schema, verrors, template_id):
        await self._ensure_unique(verrors, schema, 'name', data['name'], template_id)

        acltype = FS_ACL_Type(data['acltype'])

        for idx, ace in enumerate(data['acl']):
            # We deliberately remove `who` key from entry before datastore insertion
            # because the name can change due to account management actions
            ace_who = ace.pop('who', None)

            if ace.get('id') is None:
                ace['id'] = ACL_UNDEFINED_ID

            if ace['tag'] in NFS4_SPECIAL_ENTRIES | POSIX_SPECIAL_ENTRIES:
                continue

            if ace['id'] != ACL_UNDEFINED_ID:
                if ace_who:
                    verrors.add(f'{schema}.{idx}.who',
                                'id and who may not be simultaneously specified in ACL entry')
                continue

            if ace_who is None:
                verrors.add(f'{schema}.{idx}.id', 'identifier (uid, gid, who) is required')
                continue

            match ace['tag']:
                case 'USER':
                    entry = await self.middleware.call('user.query', [['username', '=', ace['who']]])
                    entry_key = 'uid'
                case 'GROUP':
                    entry = await self.middleware.call('group.query', [['group', '=', ace['who']]])
                    entry_key = 'gid'
                case _:
                    raise TypeError(f'{ace["tag"]}: unexpected ace tag.')

            if not entry:
                verrors.add(f'{schema}.{idx}.who', f'{ace["who"]}: {ace["tag"].lower()} does not exist')
                continue

            ace['id'] = entry[0][entry_key]

        if acltype is FS_ACL_Type.POSIX1E:
            gen_aclstring_posix1e(copy.deepcopy(data['acl']), False, verrors)

    @api_method(
        AclTemplateCreateArgs,
        AclTemplateCreateResult,
        roles=['FILESYSTEM_ATTRS_WRITE']
    )
    async def do_create(self, data):
        """
        Create a new filesystem ACL template.
        """
        verrors = ValidationErrors()
        if len(data['acl']) == 0:
            verrors.add(
                "filesystem_acltemplate_create.acl",
                "At least one ACL entry must be specified."
            )
        await self.validate_acl(data, "filesystem_acltemplate_create.acl", verrors, None)
        verrors.check()
        data['builtin'] = False

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        return await self.get_instance(data['id'])

    @api_method(
        AclTemplateUpdateArgs,
        AclTemplateUpdateResult,
        roles=['FILESYSTEM_ATTRS_WRITE']
    )
    async def do_update(self, id_, data):
        """
        update filesystem ACL template with `id`.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        if old['builtin']:
            verrors.add("filesystem_acltemplate_update.builtin",
                        "built-in ACL templates may not be changed")

        if new['name'] != old['name']:
            name_exists = bool(await self.query([('name', '=', new['name'])]))
            if name_exists:
                verrors.add("filesystem_acltemplate_update.name",
                            f"{data['name']}: name is not unique")

        if len(new['acl']) == 0:
            verrors.add(
                "filesystem_acltemplate_update.acl",
                "At least one ACL entry must be specified."
            )
        await self.validate_acl(new, "filesystem_acltemplate_update.acl", verrors, id_)
        verrors.check()

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        return await self.get_instance(id_)

    @api_method(
        AclTemplateDeleteArgs,
        AclTemplateDeleteResult,
        roles=['FILESYSTEM_ATTRS_WRITE']
    )
    async def do_delete(self, id_):
        entry = await self.get_instance(id_)
        if entry['builtin']:
            raise CallError("Deletion of builtin templates is not permitted",
                            errno.EPERM)

        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id_
        )

    @private
    async def append_builtins_internal(self, ids, data):
        """
        This method ensures that ACL grants some minimum level of permissions
        to our builtin users or builtin admins accounts.
        """
        bu_id, ba_id = ids
        has_bu = bool([x['id'] for x in data['acl'] if x['id'] == bu_id])
        has_ba = bool([x['id'] for x in data['acl'] if x['id'] == ba_id])

        if (bu_id != -1 and has_bu) or (ba_id != -1 and has_ba):
            return

        if data['acltype'] == FS_ACL_Type.NFS4:
            if bu_id != -1:
                data['acl'].append(
                    {"tag": "GROUP", "id": bu_id, "perms": {"BASIC": "MODIFY"}, "flags": {"BASIC": "INHERIT"}, "type": "ALLOW"},
                )

            if ba_id != -1:
                data['acl'].append(
                    {"tag": "GROUP", "id": ba_id, "perms": {"BASIC": "FULL_CONTROL"}, "flags": {"BASIC": "INHERIT"}, "type": "ALLOW"},
                )
            return

        has_default_mask = any(filter(lambda x: x["tag"] == "MASK" and x["default"], data['acl']))
        has_access_mask = any(filter(lambda x: x["tag"] == "MASK" and x["default"], data['acl']))
        all_perms = {"READ": True, "WRITE": True, "EXECUTE": True}
        if bu_id != -1:
            data['acl'].extend([
                {"tag": "GROUP", "id": bu_id, "perms": all_perms, "default": False},
                {"tag": "GROUP", "id": bu_id, "perms": all_perms, "default": True},
            ])

        if ba_id != -1:
            data['acl'].extend([
                {"tag": "GROUP", "id": ba_id, "perms": all_perms, "default": False},
                {"tag": "GROUP", "id": ba_id, "perms": all_perms, "default": True},
            ])

        if not has_default_mask:
            data['acl'].append({"tag": "MASK", "id": -1, "perms": all_perms, "default": False})

        if not has_access_mask:
            data['acl'].append({"tag": "MASK", "id": -1, "perms": all_perms, "default": True})

        return

    @private
    async def append_builtins(self, data):
        bu_id = int(SMBBuiltin.USERS.value[1][9:])
        ba_id = int(SMBBuiltin.ADMINISTRATORS.value[1][9:])
        await self.append_builtins_internal((bu_id, ba_id), data)

        ds = await self.middleware.call('directoryservices.status')
        if ds['type'] != DSType.AD.value or ds['status'] != DSStatus.HEALTHY.name:
            return

        domain_info = await self.middleware.call('idmap.domain_info', 'DS_TYPE_ACTIVEDIRECTORY')
        if 'ACTIVE_DIRECTORY' not in domain_info['domain_flags']['parsed']:
            self.logger.warning(
                '%s: domain is not identified properly as an Active Directory domain.',
                domain_info['dns_name']
            )
            return

        # If user has explicitly chosen to not include local builtin_users, don't add domain variant
        domain_users_sid = domain_info['sid'] + '-513'
        domain_admins_sid = domain_info['sid'] + '-512'
        idmaps = await self.middleware.call('idmap.convert_sids', [
            domain_users_sid, domain_admins_sid
        ])
        has_bu = bool([x['id'] for x in data['acl'] if x['id'] == bu_id])
        if has_bu:
            du = idmaps['mapped'].get(domain_users_sid)
        else:
            du = {'id': -1}

        da = idmaps['mapped'].get(domain_admins_sid)
        if du is None:
            self.logger.warning(
                "Failed to resolve the Domain Users group to a Unix ID. This most likely "
                "indicates a misconfiguration of idmap for the active directory domain. If "
                "The idmap backend is AD, further configuration may be required to manually "
                "assign a GID to the domain users group."
            )
            du = {'id': -1}

        if da is None:
            self.logger.warning(
                "Failed to resolve the Domain Users group to a Unix ID. This most likely "
                "indicates a misconfiguration of idmap for the active directory domain. If "
                "The idmap backend is AD, further configuration may be required to manually "
                "assign a GID to the domain users group."
            )
            da = {'id': -1}

        await self.append_builtins_internal((du['id'], da['id']), data)

    @private
    async def resolve_names(self, uid, gid, data):
        for ace in data['acl']:
            if ace['id'] not in (-1, None):
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

    @api_method(
        AclTemplateByPathArgs,
        AclTemplateByPathResult,
        roles=['FILESYSTEM_ATTRS_READ']
    )
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
            acltype = await self.middleware.call(
                'filesystem.path_get_acltype', data['path']
            )
            if acltype == FS_ACL_Type.DISABLED:
                return []

            if acltype == FS_ACL_Type.POSIX1E and data['format-options']['canonicalize']:
                verrors.add(
                    "filesystem.acltemplate_by_path.format-options.canonicalize",
                    "POSIX1E ACLs may not be sorted into Windows canonical order."
                )
            filters.append(("acltype", "=", acltype))

        if not data['path'] and data['format-options']['resolve_names']:
            verrors.add(
                "filesystem.acltemplate_by_path.format-options.resolve_names",
                "ACL entry ids may not be resolved into names unless path is provided."
            )

        verrors.check()

        templates = await self.query(filters, data['query-options'])
        for t in templates:
            if data['format-options']['ensure_builtins']:
                await self.append_builtins(t)

            if data['format-options']['resolve_names']:
                st = await self.middleware.run_in_thread(os.stat, data['path'])
                await self.resolve_names(st.st_uid, st.st_gid, t)

            if data['format-options']['canonicalize'] and t['acltype'] == FS_ACL_Type.NFS4:
                canonicalized = canonicalize_nfs4_acl(t['acl'])
                t['acl'] = canonicalized

        return templates
