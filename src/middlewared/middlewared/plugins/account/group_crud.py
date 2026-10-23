from __future__ import annotations

from asyncio import Lock as AsyncioLock
from collections import defaultdict
import errno
from typing import Any

from middlewared.api.current import (
    GroupCreate,
    GroupDeleteOptions,
    GroupEntry,
    GroupGetGroupObj,
    GroupUpdate,
    QueryOptions,
)
from middlewared.plugins.account.constants import (
    ALLOWED_BUILTIN_GIDS,
    MIN_AUTO_XID,
    USERNS_IDMAP_DIRECT,
    USERNS_IDMAP_NONE,
)
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID, IDType
from middlewared.service import CallError, CRUDServicePart, ServiceContext, ValidationErrors
from middlewared.service_exception import InstanceNotFound, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.directoryservices.constants import DSStatus
from middlewared.utils.lang import undefined
from middlewared.utils.privilege import privileges_group_mapping
from middlewared.utils.reserved_ids import ReservedXid
from middlewared.utils.sid import DomainRid, db_id_to_rid
from middlewared.utils.types import AuditCallback

from .group_validate import common_validation, validate_builtin_update, validate_userns_idmap_conflict
from .membership import GroupMembershipModel
from .utils import filters_include_ds_accounts, userns_idmap_to_db

__all__ = ("ASYNC_NEXT_GID_LOCK", "GroupModel", "GroupServicePart")

ASYNC_NEXT_GID_LOCK = AsyncioLock()


class GroupModel(sa.Model):
    __tablename__ = "account_bsdgroups"

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrp_gid = sa.Column(sa.Integer())
    bsdgrp_group = sa.Column(sa.String(120), unique=True)
    bsdgrp_builtin = sa.Column(sa.Boolean(), default=False)
    bsdgrp_sudo_commands = sa.Column(sa.JSON(list))
    bsdgrp_sudo_commands_nopasswd = sa.Column(sa.JSON(list))
    bsdgrp_smb = sa.Column(sa.Boolean(), default=True)
    bsdgrp_userns_idmap = sa.Column(sa.Integer(), default=USERNS_IDMAP_NONE)
    bsdgrp_users: sa.Mapped[list[Any]] = sa.relationship(
        "UserModel",
        secondary=lambda: GroupMembershipModel.__table__,
        overlaps="bsdusr_groups",
    )


class GroupServicePart(CRUDServicePart[GroupEntry]):
    _datastore = "account.bsdgroups"
    _datastore_prefix = "bsdgrp_"
    _entry = GroupEntry

    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)
        self.reserved_gids = ReservedXid({})

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        primary_memberships = defaultdict(set)
        for user in await self.middleware.call("datastore.query", "account.bsdusers"):
            primary_memberships[user["bsdusr_group"]["id"]].add(user["id"])

        return {
            "privileges": await self.middleware.call("datastore.query", "account.privilege"),
            "primary_memberships": primary_memberships,
            "server_sid": await self.middleware.call("smb.local_server_sid"),
        }

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data["name"] = data["group"]
        data["users"] = list({u["id"] for u in data["users"]} | context["primary_memberships"][data["id"]])

        privilege_mappings = privileges_group_mapping(context["privileges"], [data["gid"]], "local_groups")

        if data["userns_idmap"] == USERNS_IDMAP_DIRECT:
            data["userns_idmap"] = "DIRECT"
        elif data["userns_idmap"] == USERNS_IDMAP_NONE:
            data["userns_idmap"] = None

        sid: str | None
        match data["group"]:
            case "builtin_administrators":
                sid = f"{context['server_sid']}-{DomainRid.ADMINS}"
            case "builtin_guests":
                sid = f"{context['server_sid']}-{DomainRid.GUESTS}"
            case _:
                if data["smb"]:
                    sid = f"{context['server_sid']}-{db_id_to_rid(IDType.GROUP, data['id'])}"
                else:
                    sid = None

        data.update(
            {
                "local": True,
                "sid": sid,
                "immutable": data["builtin"] and data["gid"] not in ALLOWED_BUILTIN_GIDS,
                "roles": privilege_mappings["roles"],
            }
        )
        return data

    async def _query_rows(
        self,
        filters: list[Any],
        options: QueryOptions,
        extra: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows = await super()._query_rows(filters, options, extra)
        if not filters_include_ds_accounts(filters):
            return rows

        ds = await self.middleware.call("directoryservices.status")
        if ds["type"] is None or ds["status"] != DSStatus.HEALTHY.name:
            return rows

        # The cache stores whole `GroupEntry` rows and applies `filters` itself, so these
        # must not be extended again.
        ds_groups: list[dict[str, Any]] = await self.middleware.call(
            "directoryservices.cache.query",
            "GROUP",
            filters,
            options.model_dump(),
        )
        return rows + ds_groups

    async def get_instance(self, id_: int, extra: dict[str, Any] | None = None) -> GroupEntry:
        groups = await self.query([[self._datastore_primary_key, "=", id_]])
        if not groups:
            raise InstanceNotFound(f"Group {id_} does not exist")

        return groups[0]

    async def do_create(self, data: GroupCreate, reload_users: bool = True) -> int:
        verrors = ValidationErrors()
        await common_validation(self, verrors, data, "group_create")
        verrors.check()

        gid = data.gid
        if gid is None:
            gid = await self.get_next_gid()

            # common_validation could not resolve a DIRECT mapping without a gid;
            # now that one was auto-assigned, recheck against existing idmap claims.
            idmap_verrors = ValidationErrors()
            await validate_userns_idmap_conflict(
                self,
                idmap_verrors,
                "group_create",
                data.userns_idmap,
                gid,
                None,
            )
            if idmap_verrors:
                async with ASYNC_NEXT_GID_LOCK:
                    self.reserved_gids.remove_entry(gid)
                idmap_verrors.check()

        row = {
            "group": data.name,
            "gid": gid,
            "smb": data.smb,
            "sudo_commands": data.sudo_commands,
            "sudo_commands_nopasswd": data.sudo_commands_nopasswd,
            "userns_idmap": userns_idmap_to_db(data.userns_idmap),
            "users": data.users,
        }

        try:
            pk: int = await self.middleware.call(
                "datastore.insert",
                self._datastore,
                row,
                {"prefix": self._datastore_prefix},
            )
        finally:
            # Once the data store entry is created we can safely remove the reservation
            async with ASYNC_NEXT_GID_LOCK:
                self.reserved_gids.remove_entry(gid)

        if reload_users:
            await self._reload_users()

        if data.smb:
            await self.middleware.call("smb.add_groupmap", {"id": pk, "gid": gid, "group": data.name})

        return pk

    async def do_update(self, audit_callback: AuditCallback, id_: int, data: GroupUpdate) -> int:
        if id_ > BASE_SYNTHETIC_DATASTORE_ID:
            audit_callback(await self._directory_service_group_name(id_))
            raise CallError(
                "Groups provided by a directory service must be modified through the identity provider "
                "(LDAP server or domain controller).",
                errno.EPERM,
            )

        group = await self.get_instance(id_)
        audit_callback(group.name)

        verrors = ValidationErrors()
        await common_validation(self, verrors, data, "group_update", pk=id_)
        if group.immutable:
            verrors.add("group_update.id", "Immutable groups cannot be changed")
        elif group.builtin:
            validate_builtin_update(verrors, group, data)

        verrors.check()

        new = group.updated(data)
        renamed = getattr(data, "name") is not undefined and new.name != group.group

        if renamed:
            if new.smb:
                # group renamed. We can simply add over top since group_mapping.tdb is keyed
                # by SID value
                await self.middleware.call("smb.add_groupmap", {"id": id_, "gid": new.gid, "group": new.name})
        elif new.smb and not group.smb:
            await self.middleware.call("smb.add_groupmap", {"id": id_, "gid": new.gid, "group": new.name})
        elif group.smb and not new.smb:
            await self.middleware.call("smb.del_groupmap", id_)

        primary_users = {
            user["id"]
            for user in await self.middleware.call(
                "datastore.query",
                "account.bsdusers",
                [("bsdusr_group", "=", id_)],
            )
        }

        await self.middleware.call(
            "datastore.update",
            self._datastore,
            id_,
            {
                "group": new.name,
                "gid": new.gid,
                "smb": new.smb,
                "sudo_commands": new.sudo_commands,
                "sudo_commands_nopasswd": new.sudo_commands_nopasswd,
                "userns_idmap": userns_idmap_to_db(new.userns_idmap),
                "users": [user_id for user_id in new.users if user_id not in primary_users],
            },
            {"prefix": self._datastore_prefix},
        )

        await self._reload_users()
        return id_

    async def do_delete(self, audit_callback: AuditCallback, id_: int, options: GroupDeleteOptions) -> int:
        if id_ > BASE_SYNTHETIC_DATASTORE_ID:
            audit_callback(await self._directory_service_group_name(id_))
            raise CallError(
                "Groups provided by a directory service must be deleted from the identity provider "
                "(LDAP server or domain controller).",
                errno.EPERM,
            )

        group = await self.get_instance(id_)
        if options.delete_users:
            audit_callback(f"{group.name} and all users that have this group as their primary group")
        else:
            audit_callback(group.name)

        if group.builtin:
            raise CallError("A built-in group cannot be deleted.", errno.EACCES)

        await self.call2(self.s.privilege.before_group_delete, group)

        nogroup = await self.middleware.call(
            "datastore.query",
            self._datastore,
            [("group", "=", "nogroup")],
            {"prefix": self._datastore_prefix, "get": True},
        )

        for user in await self.middleware.call(
            "datastore.query",
            "account.bsdusers",
            [("group", "=", id_)],
            {"prefix": "bsdusr_"},
        ):
            if options.delete_users:
                await self.middleware.call("datastore.delete", "account.bsdusers", user["id"])
            else:
                await self.middleware.call(
                    "datastore.update",
                    "account.bsdusers",
                    user["id"],
                    {"group": nogroup["id"]},
                    {"prefix": "bsdusr_"},
                )

        await self.middleware.call("datastore.delete", self._datastore, id_)

        if group.smb:
            await self.middleware.call("smb.del_groupmap", id_)

        await self._reload_users()
        try:
            await self.middleware.call(
                "idmap.gencache.del_idmap_cache_entry",
                {
                    "entry_type": "GID2SID",
                    "entry": group.gid,
                },
            )
        except MatchNotFound:
            pass

        return id_

    async def get_next_gid(self) -> int:
        async with ASYNC_NEXT_GID_LOCK:
            groups = await self.middleware.call(
                "datastore.query", self._datastore, [["bsdgrp_gid", ">=", MIN_AUTO_XID], ["bsdgrp_builtin", "=", False]]
            )
            used_gids = {group["bsdgrp_gid"] for group in groups}
            used_gids |= {
                gid
                for gid in (await self.call2(self.s.privilege.used_local_gids)).keys()
                if gid >= MIN_AUTO_XID
            }
            total_gids = used_gids | self.reserved_gids.in_use()
            if total_gids:
                max_gid = max(total_gids)
            else:
                max_gid = MIN_AUTO_XID - 1

            if gid_gap := (set(range(MIN_AUTO_XID, max_gid)) - total_gids):
                next_gid = min(gid_gap)
            else:
                next_gid = max_gid + 1

            self.reserved_gids.add_entry(next_gid)
            return next_gid

    async def _reload_users(self) -> None:
        await (await self.call2(self.s.service.control, "RELOAD", "user")).wait(raise_error=True)

    async def _directory_service_group_name(self, id_: int) -> str:
        # datastore ids for directory services are created by adding the
        # posix ID to a base value so that we can use getpwuid / getgrgid to
        # convert back to a username / group name
        try:
            group_obj = await self.call2(
                self.s.group.get_group_obj,
                GroupGetGroupObj(gid=id_ - BASE_SYNTHETIC_DATASTORE_ID),
            )
        except KeyError:
            return "UNKNOWN"

        return group_obj.gr_name
