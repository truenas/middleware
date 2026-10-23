from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from middlewared.api.current import GroupEntry, UserEntry
from middlewared.service import CallError
from middlewared.utils.privilege import BuiltinPrivileges

from .password import unixhash_is_valid

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("before_group_delete", "before_user_deactivation", "local_administrators", "used_local_gids")


async def used_local_gids(context: ServiceContext) -> dict[int, dict[str, Any]]:
    gids: dict[int, dict[str, Any]] = {}
    for privilege in await context.middleware.call(
        "datastore.query",
        "account.privilege",
        [],
        {"order_by": ["id"]},
    ):
        for gid in privilege["local_groups"]:
            gids.setdefault(gid, privilege)

    return gids


async def before_user_deactivation(context: ServiceContext, user: UserEntry, error_text: str) -> None:
    for privilege in await context.middleware.call(
        "datastore.query",
        "account.privilege",
        [["builtin_name", "=", BuiltinPrivileges.LOCAL_ADMINISTRATOR.value]],
    ):
        if not await context.call2(
            context.s.group.has_password_enabled_user,
            privilege["local_groups"],
            [user.id],
        ):
            raise CallError(
                f"{error_text} will have built-in privilege {privilege['name']!r}.",
                errno.EACCES,
            )


async def before_group_delete(context: ServiceContext, group: GroupEntry) -> None:
    for privilege in await context.middleware.call("datastore.query", "account.privilege"):
        if group.gid in privilege["local_groups"]:
            raise CallError(
                f"This group is used by privilege {privilege['name']!r}. Please remove it from that privilege "
                "first, then delete the group.",
                errno.EACCES,
            )


async def local_administrators(
    context: ServiceContext,
    exclude_user_ids: list[int] | None = None,
    users: list[UserEntry] | None = None,
    groups: list[GroupEntry] | None = None,
) -> list[UserEntry]:
    exclude_user_ids = exclude_user_ids or []
    if users is None:
        users = await context.call2(context.s.user.query, [["local", "=", True]])
    if groups is None:
        groups = await context.call2(context.s.group.query, [["local", "=", True]])

    local_administrator_privilege = await context.middleware.call(
        "datastore.query",
        "account.privilege",
        [["builtin_name", "=", BuiltinPrivileges.LOCAL_ADMINISTRATOR.value]],
        {"get": True},
    )
    rows: list[dict[str, Any]] = await context.call2(
        context.s.group.get_password_enabled_users,
        local_administrator_privilege["local_groups"],
        exclude_user_ids,
        groups,
    )
    by_id = {user.id: user for user in users}
    administrators = [by_id[row["id"]] for row in rows]
    if not administrators:
        root_user = next(u for u in users if u.username == "root")
        if root_user.id not in exclude_user_ids:
            if unixhash_is_valid(root_user.unixhash.get_secret_value()):
                # This can only be if `always_has_root_password_enabled` is `True`
                administrators = [root_user]

    return administrators
