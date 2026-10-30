from __future__ import annotations

import errno
from typing import Any

from middlewared.api.current import GroupEntry, PrivilegeCreate, PrivilegeEntry, PrivilegeUpdate, UnmappedGroupEntry
from middlewared.service import CallError, CRUDServicePart, ServiceContext, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.directoryservices.constants import DSStatus
from middlewared.utils.privilege import BuiltinPrivileges
from middlewared.utils.privilege_constants import LocalBuiltinAdminGroups
from middlewared.utils.types import AuditCallback

from .privilege_admins import local_administrators
from .privilege_groups import get_groups, resolve_ds_groups, resolve_local_groups
from .privilege_validate import validate_privilege

__all__ = ("PrivilegeModel", "PrivilegeServicePart")


class PrivilegeModel(sa.Model):
    __tablename__ = "account_privilege"

    id = sa.Column(sa.Integer(), primary_key=True)
    builtin_name = sa.Column(sa.String(200), nullable=True)
    name = sa.Column(sa.String(200))
    local_groups = sa.Column(sa.JSON(list))
    ds_groups = sa.Column(sa.JSON(list))
    roles = sa.Column(sa.JSON(list))
    web_shell = sa.Column(sa.Boolean())


def to_payload(privilege: PrivilegeEntry) -> PrivilegeCreate:
    """The stored privilege in the shape a caller would have supplied it.

    `query` reports the grantee lists as resolved group entries, so they have to be reduced back to
    the group IDs that are actually stored before an update payload can be applied on top.
    """
    ds_groups: list[int | str] = []
    for group in privilege.ds_groups:
        # Preference is for SID values rather than GIDS because they are universally unique
        if group.sid:
            ds_groups.append(group.sid)
        elif group.gid is not None:
            ds_groups.append(group.gid)

    return PrivilegeCreate(
        name=privilege.name,
        # a local group that could not be resolved still reports the GID it is configured with
        local_groups=[group.gid for group in privilege.local_groups if group.gid is not None],
        ds_groups=ds_groups,
        roles=privilege.roles,
        web_shell=privilege.web_shell,
    )


class PrivilegeServicePart(CRUDServicePart[PrivilegeEntry]):
    _datastore = "account.privilege"
    _datastore_sql_filters = frozenset(("id", "builtin_name", "name", "web_shell"))
    _entry = PrivilegeEntry

    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)
        self.previous_always_has_root_password_enabled: bool | None = None

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {"groups": await get_groups(self)}

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        groups = context["groups"]
        data["local_groups"] = resolve_local_groups(groups, data["local_groups"])
        data["ds_groups"] = await resolve_ds_groups(self, groups, data["ds_groups"])
        return data

    async def do_create(self, data: PrivilegeCreate) -> PrivilegeEntry:
        await validate_privilege(self, "privilege_create", data)

        return await self._create(data.model_dump())

    async def do_update(self, audit_callback: AuditCallback, id_: int, data: PrivilegeUpdate) -> PrivilegeEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        new = to_payload(old).updated(data)

        verrors = ValidationErrors()

        if old.builtin_name:
            for field in ("name", "roles"):
                if getattr(new, field) != getattr(old, field):
                    verrors.add(f"privilege_update.{field}", "This field is read-only for built-in privileges")

            builtin_privilege = BuiltinPrivileges(old.builtin_name)

            if builtin_privilege == BuiltinPrivileges.LOCAL_ADMINISTRATOR:
                if LocalBuiltinAdminGroups.BUILTIN_ADMINISTRATORS not in new.local_groups:
                    verrors.add(
                        "privilege_update.local_groups",
                        f"The group {LocalBuiltinAdminGroups.BUILTIN_ADMINISTRATORS.name.lower()} must be "
                        'among grantees of the "Local Administrator" privilege.',
                    )

                if not await self.call2(self.s.group.has_password_enabled_user, new.local_groups):
                    verrors.add(
                        "privilege_update.local_groups",
                        "None of the members of these groups has password login enabled. At least one grantee of "
                        'the "Local Administrator" privilege must have password login enabled.',
                    )
            elif builtin_privilege == BuiltinPrivileges.READONLY_ADMINISTRATOR:
                if new.web_shell:
                    verrors.add(
                        "privilege_update.web_shell",
                        "Web shell access may not be enabled for the built-in group for read-only administrators.",
                    )

        if removed_unmapped := [
            group.sid or group.gid
            for group in old.ds_groups
            if isinstance(group, UnmappedGroupEntry)
            and group.sid not in new.ds_groups
            and group.gid not in new.ds_groups
        ]:
            # No directory service group resolves while directory services are unhealthy, so these may still exist
            ds = await self.middleware.call("directoryservices.status")
            if ds["type"] is not None and ds["status"] != DSStatus.HEALTHY.name:
                verrors.add(
                    "privilege_update.ds_groups",
                    f"{', '.join(map(str, removed_unmapped))}: directory service groups may not be removed from a "
                    "privilege while the directory service state is unhealthy, because they cannot be resolved.",
                )

        verrors.check()

        await validate_privilege(self, "privilege_update", new, id_)

        return await self._update(id_, new.model_dump())

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> bool:
        privilege = await self.get_instance(id_)
        audit_callback(privilege.name)

        if privilege.builtin_name:
            raise CallError("Unable to delete built-in privilege", errno.EPERM)

        deleted: bool = await self.middleware.call("datastore.delete", self._datastore, id_)
        return deleted

    async def always_has_root_password_enabled(
        self,
        users: list[dict[str, Any]] | None = None,
        groups: list[GroupEntry] | None = None,
    ) -> bool:
        if users is None:
            users = await self.middleware.call("user.query", [["local", "=", True]])
        if groups is None:
            groups = await self.call2(self.s.group.query, [["local", "=", True]])

        root_user = next(u for u in users if u["username"] == "root")
        administrators = await local_administrators(self, [root_user["id"]], users, groups)
        if not administrators:
            value = True
        else:
            value = False

            if self.previous_always_has_root_password_enabled:
                usernames = [user["username"] for user in administrators]
                self.middleware.send_event(
                    "user.web_ui_login_disabled",
                    "ADDED",
                    id=None,
                    fields={"usernames": usernames},
                )

        self.previous_always_has_root_password_enabled = value
        return value
