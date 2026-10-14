from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from middlewared.api.current import GroupCreate, GroupEntry, GroupGetGroupObj, GroupUpdate, QueryOptions
from middlewared.plugins.account import validate_sudo_commands
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID
from middlewared.plugins.smb_.constants import SMBBuiltin
from middlewared.service import ValidationErrors
from middlewared.utils.lang import undefined

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


async def validate_userns_idmap_conflict(
    context: ServiceContext,
    verrors: ValidationErrors,
    schema: str,
    userns_idmap: str | int | None,
    gid: int | None,
    exclude_id: int | None = None,
) -> None:
    """Verify the proposed userns_idmap doesn't collide with another local group's mapping.

    `gid` is the group's host GID; it may be None during creation if not yet auto-assigned,
    in which case a DIRECT mapping cannot be resolved and the check is deferred. Callers
    that auto-assign the GID must re-invoke this check after assignment.
    """
    if not userns_idmap:
        return

    proposed: str | int | None
    if userns_idmap == "DIRECT":
        proposed = gid
    else:
        proposed = userns_idmap

    if proposed is None:
        return

    conflict_filters: list[Any] = [
        ["local", "=", True],
        ["userns_idmap", "nin", [None, 0]],
    ]
    if exclude_id is not None:
        conflict_filters.append(["id", "!=", exclude_id])

    for other in await context.call2(context.s.group.query, conflict_filters):
        other_target: str | int | None
        if other.userns_idmap == "DIRECT":
            other_target = other.gid
        else:
            other_target = other.userns_idmap

        if other_target == proposed:
            verrors.add(f"{schema}.userns_idmap", f"Group {other.name!r} already maps to container GID {proposed}.")
            return


async def common_validation(
    context: ServiceContext,
    verrors: ValidationErrors,
    data: GroupCreate | GroupUpdate,
    schema: str,
    pk: int | None = None,
) -> None:
    if pk:
        exclude_filter: list[Any] = [("id", "!=", pk)]
    else:
        exclude_filter = []

    smb: Any = getattr(data, "smb")
    name: Any = getattr(data, "name")
    gid: Any = getattr(data, "gid", undefined)
    users: Any = getattr(data, "users")
    userns_idmap: Any = getattr(data, "userns_idmap")
    sudo_commands: Any = getattr(data, "sudo_commands")
    sudo_commands_nopasswd: Any = getattr(data, "sudo_commands_nopasswd")

    if smb is not undefined and smb and not await context.middleware.call("smb.is_configured"):
        verrors.add(f"{schema}.smb", "SMB groups may not be configured while SMB service backend is unitialized.")

    entry = None
    if pk and userns_idmap is not undefined:
        entry = await context.call2(
            context.s.group.query,
            [["local", "=", True], ["id", "=", pk]],
            QueryOptions(get=True),
        )
        if entry.roles:
            verrors.add(
                f"{schema}.userns_idmap", "User namespace idmaps may not be configured for privileged accounts."
            )

        if entry.builtin:
            verrors.add(f"{schema}.userns_idmap", "User namespace idmaps may not be configured for builtin accounts.")

    effective_gid: int | None
    if entry:
        effective_gid = entry.gid
    elif gid is undefined:
        effective_gid = None
    else:
        effective_gid = gid

    if userns_idmap is not undefined:
        await validate_userns_idmap_conflict(
            context,
            verrors,
            schema,
            userns_idmap,
            effective_gid,
            exclude_id=pk,
        )

    if name is not undefined:
        if smb is not undefined and smb:
            if name.upper() in [x.name for x in SMBBuiltin]:
                verrors.add(
                    f"{schema}.name",
                    f'Group name "{name}" conflicts with existing SMB Builtin entry. '
                    f"SMB group mapping is not permitted for this group.",
                    errno.EEXIST,
                )

            smb_groups = await context.middleware.call(
                "datastore.query",
                "account.bsdgroups",
                [("smb", "=", True)] + exclude_filter,
                {"prefix": "bsdgrp_"},
            )

            if any(g["group"].casefold() == name.casefold() for g in smb_groups):
                verrors.add(
                    f"{schema}.name",
                    f'Group name "{name}" conflicts with existing groupmap entry. '
                    f"SMB group mapping is not permitted for this group. Note that SMB "
                    f"group names are case-insensitive.",
                    errno.EEXIST,
                )

        if await context.middleware.call(
            "datastore.query",
            "account.bsdgroups",
            [("group", "=", name)] + exclude_filter,
            {"prefix": "bsdgrp_"},
        ):
            verrors.add(
                f"{schema}.name",
                f'A Group with the name "{name}" already exists.',
                errno.EEXIST,
            )

    if gid is not undefined and gid is not None:
        try:
            existing = await context.call2(context.s.group.get_group_obj, GroupGetGroupObj(gid=gid))
        except KeyError:
            pass
        else:
            verrors.add(
                f"{schema}.gid",
                f"Gid {gid} is already used (group {existing.gr_name} has it)",
                errno.EEXIST,
            )

        if privilege := (await context.middleware.call("privilege.used_local_gids")).get(gid):
            verrors.add(
                f"{schema}.gid",
                f"A privilege {privilege['name']!r} already uses this group ID.",
                errno.EINVAL,
            )

    if users is not undefined:
        for idx, dbid in enumerate(users):
            if dbid >= BASE_SYNTHETIC_DATASTORE_ID:
                verrors.add(
                    f"{schema}.users.{idx}", "Directory services users may not be added as members of local groups."
                )
                return

    root_user = await context.middleware.call("user.query", [("username", "=", "root")], {"get": True})
    root_user_id = root_user["id"]
    if pk:
        pk_groupname: str | None = (await context.call2(context.s.group.get_instance, pk)).group
    else:
        pk_groupname = None

    if users is not undefined:
        # Block root user from new groups or
        # added to any groups other than BUILTIN_ADMINISTRATORS
        if (schema == "group_create" or (pk_groupname != "builtin_administrators")) and (root_user_id in users):
            verrors.add(f"{schema}.users", "Cannot add the root user to this group")

        existing_users = {
            i["id"] for i in await context.middleware.call("datastore.query", "account.bsdusers", [("id", "in", users)])
        }
        if notfound := set(users) - existing_users:
            verrors.add(
                f"{schema}.users",
                f"Following users do not exist: {', '.join(map(str, notfound))}",
            )

        removed_primary_users = []
        for user in await context.middleware.call(
            "datastore.query",
            "account.bsdusers",
            [("bsdusr_group", "=", pk)],
        ):
            if user["id"] not in users:
                removed_primary_users.append(user["bsdusr_username"])

        if removed_primary_users:
            verrors.add(
                f"{schema}.users",
                f"This group is primary for the following users: {', '.join(removed_primary_users)}. "
                "You can't remove them.",
            )

        if pk and pk_groupname == "builtin_administrators" and root_user_id not in users:
            verrors.add(f"{schema}.users", "The root user must remain a member of the builtin_administrators group.")

    if sudo_commands is not undefined:
        verrors.add_child(
            f"{schema}.sudo_commands",
            await context.to_thread(validate_sudo_commands, sudo_commands),
        )

    if sudo_commands_nopasswd is not undefined:
        verrors.add_child(
            f"{schema}.sudo_commands_nopasswd",
            await context.to_thread(validate_sudo_commands, sudo_commands_nopasswd),
        )


def validate_builtin_update(verrors: ValidationErrors, group: GroupEntry, data: GroupUpdate) -> None:
    # Generally many features of builtin groups should be immutable
    for key in ("sudo_commands", "sudo_commands_nopasswd", "smb", "name"):
        value = getattr(data, key)
        if value is undefined or value is None:
            continue

        if value != getattr(group, key):
            verrors.add(f"group_update.{key}", "This configuration parameter may not be changed for builtin groups.")
