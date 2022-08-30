import enum
import errno

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, Str, Patch
from middlewared.service import CallError, CRUDService, private, ValidationErrors
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa


class BuiltinPrivileges(enum.Enum):
    LOCAL_ADMINISTRATOR = "LOCAL_ADMINISTRATOR"


class PrivilegeModel(sa.Model):
    __tablename__ = "account_privilege"

    id = sa.Column(sa.Integer(), primary_key=True)
    builtin_name = sa.Column(sa.String(200), nullable=True)
    name = sa.Column(sa.String(200))
    local_groups = sa.Column(sa.JSON(type=list))
    ds_groups = sa.Column(sa.JSON(type=list))
    allowlist = sa.Column(sa.JSON(type=list))
    web_shell = sa.Column(sa.Boolean())


class PrivilegeService(CRUDService):

    keys = {}

    class Config:
        namespace = "privilege"
        datastore = "account.privilege"
        datastore_extend = "privilege.item_extend"
        datastore_extend_context = "privilege.item_extend_context"
        cli_namespace = "auth.privilege"

    ENTRY = Dict(
        "privilege_entry",
        Int("id"),
        Str("builtin_name", null=True),
        Str("name", required=True, empty=False),
        List("local_groups", items=[Int("local_group")]),
        List("ds_groups", items=[Int("ds_group")]),
        List("allowlist", items=[Ref("allowlist_item")]),
        Bool("web_shell", required=True),
    )

    @private
    async def item_extend_context(self, rows, extra):
        return {
            "groups": await self._groups(),
        }

    @private
    async def item_extend(self, item, context):
        item["local_groups"] = self._local_groups(context["groups"], item["local_groups"])
        item["ds_groups"] = await self._ds_groups(context["groups"], item["ds_groups"])
        return item

    @accepts(Patch(
        "privilege_entry",
        "privilege_create",
        ("rm", {"name": "builtin_name"}),
    ))
    async def do_create(self, data):
        """
        Creates a privilege.

        `name` is a name for privilege (must be unique).

        `local_groups` is a list of local user account group GIDs that gain this privilege.

        `ds_groups` is list of Directory Service group GIDs that will gain this privilege.

        `allowlist` is a list of API endpoints allowed for this privilege.

        `web_shell` controls whether users with this privilege are allowed to log in to the Web UI.
        """
        await self._validate("privilege_create", data)

        id = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data
        )

        return await self.get_instance(id)

    @accepts(
        Int("id", required=True),
        Patch(
            "privilege_entry",
            "privilege_update",
            ("rm", {"name": "builtin_name"}),
            ("attr", {"update": True}),
        )
    )
    async def do_update(self, id, data):
        """
        Update the privilege `id`.
        """
        old = await self.get_instance(id)
        new = old.copy()
        new["local_groups"] = [g["gid"] for g in new["local_groups"]]
        new["ds_groups"] = [g["gid"] for g in new["ds_groups"]]
        new.update(data)

        verrors = ValidationErrors()

        if new["builtin_name"]:
            for k in ["name", "allowlist"]:
                if new[k] != old[k]:
                    verrors.add(f"privilege_update.{k}", "This field is read-only for built-in privileges")

            builtin_privilege = BuiltinPrivileges(new["builtin_name"])

            if builtin_privilege == BuiltinPrivileges.LOCAL_ADMINISTRATOR:
                if not await self.middleware.call("group.has_password_enabled_user", new["local_groups"]):
                    verrors.add(
                        "privilege_update.local_groups",
                        "None of the members of these groups has password login enabled. At least one grantee of "
                        "the \"Local Administrator\" privilege must have password login enabled."
                    )

        verrors.check()

        new.update(data)

        await self._validate("privilege_update", new, id)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id,
            new,
        )

        return await self.get_instance(id)

    @accepts(
        Int("id")
    )
    async def do_delete(self, id):
        """
        Delete the privilege `id`.
        """
        privilege = await self.get_instance(id)
        if privilege["builtin_name"]:
            raise CallError("Unable to delete built-in privilege", errno.EPERM)

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id
        )

        return response

    async def _validate(self, schema_name, data, id=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id)

        groups = await self._groups()
        for i, local_group_id in enumerate(data["local_groups"]):
            if not self._local_groups(groups, [local_group_id], include_nonexistent=False):
                verrors.add(f"{schema_name}.local_groups.{i}", "This local group does not exist")
        for i, ds_group_id in enumerate(data["ds_groups"]):
            if not await self._ds_groups(groups, [ds_group_id], include_nonexistent=False):
                verrors.add(f"{schema_name}.ds_groups.{i}", "This Directory Service group does not exist")

        if verrors:
            raise verrors

    async def _groups(self):
        return {
            group["gid"]: group
            for group in await self.middleware.call(
                "group.query",
                [],
                {"extra": {"additional_information": ["DS"]}},
            )
        }

    def _local_groups(self, groups, local_groups, *, include_nonexistent=True):
        result = []
        for gid in local_groups:
            if group := groups.get(gid):
                if group["local"]:
                    result.append(group)
            else:
                if include_nonexistent:
                    result.append({
                        "gid": gid,
                        "group": None,
                    })

        return result

    async def _ds_groups(self, groups, ds_groups, *, include_nonexistent=True):
        result = []
        for gid in ds_groups:
            if (group := groups.get(gid)) is None:
                try:
                    group = await self.middleware.call(
                        "group.query",
                        [["gid", "=", gid]],
                        {
                            "extra": {"additional_information": ["DS"]},
                            "get": True,
                        },
                    )
                except MatchNotFound:
                    if include_nonexistent:
                        result.append({
                            "gid": gid,
                            "group": None,
                        })

                    continue

            if group["local"]:
                continue

            result.append(group)

        return result

    @private
    async def before_user_delete(self, user):
        for privilege in await self.middleware.call(
            'datastore.query',
            'account.privilege',
            [['builtin_name', '!=', None]],
        ):
            if not await self.middleware.call('group.has_password_enabled_user', privilege['local_groups'],
                                              [user['id']]):
                raise CallError(
                    f'After deleting this user no local user will have built-in privilege {privilege["name"]!r}.',
                    errno.EACCES,
                )

    @private
    async def before_group_delete(self, group):
        for privilege in await self.middleware.call('datastore.query', 'account.privilege'):
            if group['gid'] in privilege['local_groups']:
                raise CallError(
                    f'This group is used by privilege {privilege["name"]!r}. Please remove it from that privilege'
                    'first, then delete the group.',
                    errno.EACCES,
                )

    @private
    async def used_local_gids(self):
        gids = {}
        for privilege in await self.middleware.call('datastore.query', 'account.privilege', [], {'order_by': ['id']}):
            for gid in privilege['local_groups']:
                gids.setdefault(gid, privilege)

        return gids

    @private
    async def compose_privilege(self, privileges):
        compose = {
            'allowlist': [],
            'web_shell': False,
        }
        for privilege in privileges:
            for item in privilege['allowlist']:
                compose['allowlist'].append(item)

            compose['web_shell'] |= privilege['web_shell']

        return compose
