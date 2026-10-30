from __future__ import annotations

import errno
import json
from typing import TYPE_CHECKING

from middlewared.api.current import GroupGetGroupObj, UserGetUserObj, UserSetupLocalAdministratorOptions
from middlewared.service import CallError
from middlewared.utils import run

from .constants import ADMIN_GID, ADMIN_UID

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("has_local_administrator_set_up", "setup_local_administrator")


async def has_local_administrator_set_up(context: ServiceContext) -> bool:
    return len(await context.call2(context.s.privilege.local_administrators)) > 0


async def setup_local_administrator(
    context: ServiceContext,
    username: str,
    password: str,
    options: UserSetupLocalAdministratorOptions,
) -> None:
    if await context.call2(context.s.user.has_local_administrator_set_up):
        raise CallError("Local administrator is already set up", errno.EEXIST)

    if username == "truenas_admin":
        # first check based on NSS to catch collisions with AD / LDAP users
        try:
            pwd_obj = await context.call2(context.s.user.get_user_obj, UserGetUserObj(uid=ADMIN_UID))
            raise CallError(
                f"A {pwd_obj.source.lower()} user with uid={ADMIN_UID} already exists, "
                "setting up local administrator is not possible",
                errno.EEXIST,
            )
        except KeyError:
            pass

        try:
            pwd_obj = await context.call2(context.s.user.get_user_obj, UserGetUserObj(username=username))
            raise CallError(
                f"{username!r} {pwd_obj.source.lower()} user already exists, "
                "setting up local administrator is not possible",
                errno.EEXIST,
            )
        except KeyError:
            pass

        try:
            grp_obj = await context.call2(context.s.group.get_group_obj, GroupGetGroupObj(gid=ADMIN_GID))
            raise CallError(
                f"A {grp_obj.source.lower()} group with gid={ADMIN_GID} already exists, "
                "setting up local administrator is not possible",
                errno.EEXIST,
            )
        except KeyError:
            pass

        try:
            grp_obj = await context.call2(context.s.group.get_group_obj, GroupGetGroupObj(groupname=username))
            raise CallError(
                f"{username!r} {grp_obj.source.lower()} group already exists, "
                "setting up local administrator is not possible",
                errno.EEXIST,
            )
        except KeyError:
            pass

        # double-check our database in case we have for some reason failed to write to passwd
        local_users = await context.call2(context.s.user.query, [["local", "=", True]])
        local_groups = await context.call2(context.s.group.query, [["local", "=", True]])

        if any(u.uid == ADMIN_UID for u in local_users):
            raise CallError(
                f"A user with uid={ADMIN_UID} already exists, setting up local administrator is not possible",
                errno.EEXIST,
            )

        if any(u.username == username for u in local_users):
            raise CallError(
                f"{username!r} user already exists, setting up local administrator is not possible",
                errno.EEXIST,
            )

        if any(g.gid == ADMIN_GID for g in local_groups):
            raise CallError(
                f"A group with gid={ADMIN_GID} already exists, setting up local administrator is not possible",
                errno.EEXIST,
            )

        if any(g.group == username for g in local_groups):
            raise CallError(
                f"{username!r} group already exists, setting up local administrator is not possible",
                errno.EEXIST,
            )

    await run(
        "truenas-set-authentication-method.py",
        check=True,
        encoding="utf-8",
        errors="ignore",
        input=json.dumps({"username": username, "password": password}),
    )
    await context.middleware.call("failover.datastore.force_send")
    await context.middleware.call("etc.generate", "user")
