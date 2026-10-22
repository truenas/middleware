from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Any, Literal

from middlewared.api.current import ComposedPrivilege
from middlewared.utils.privilege import privilege_has_webui_access, privileges_group_mapping
from middlewared.utils.privilege_constants import ALLOW_LIST_FULL_ADMIN
from middlewared.utils.security import system_security_config_to_stig_type

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = (
    "GroupsKey",
    "compose_privilege",
    "full_privilege",
    "privileges_for_groups",
    "roles_for_user",
)

GroupsKey = Literal["local_groups", "ds_groups"]
"""Which of a privilege's two grantee lists a group list is to be matched against."""


async def compose_privilege(context: ServiceContext, privileges: list[dict[str, Any]]) -> ComposedPrivilege:
    security_config = await context.call2(context.s.system.security.config)
    enabled_stig = system_security_config_to_stig_type(security_config)
    role_manager = context.middleware.role_manager

    roles: set[str] = set()
    allowlist: list[dict[str, str]] = []
    web_shell = False
    webui_access = False
    for privilege in privileges:
        for role in privilege["roles"]:
            roles |= role_manager.roles_for_role(role, enabled_stig)

            allowlist.extend(role_manager.allowlist_for_role(role, enabled_stig))

        web_shell |= privilege["web_shell"]
        webui_access |= privilege_has_webui_access(privilege)

    return ComposedPrivilege(
        roles=roles,
        allowlist=allowlist,
        # No privilege grants web shell access while STIG is enabled
        web_shell=web_shell and not enabled_stig,
        webui_access=webui_access,
    )


def full_privilege() -> ComposedPrivilege:
    return ComposedPrivilege(
        roles={"FULL_ADMIN"},
        allowlist=[ALLOW_LIST_FULL_ADMIN.copy()],
        web_shell=True,
        webui_access=True,
    )


async def privileges_for_groups(
    context: ServiceContext,
    groups_key: GroupsKey,
    group_ids: Collection[int],
) -> list[dict[str, Any]]:
    """
    group_ids here are based on NSS group_list output.

    Directory services groups may have privileges assigned by SID, which
    are set on the domain controller rather than locally on TrueNAS.

    This means we expand the set of group_ids to include SID mappings for
    permissions evaluation.

    If for some reason libwbclient raises an exception during the attempt
    to convert unix gids to SIDs, then the domain is probably unhealthy and
    permissions failure is acceptable. We do not need to log here as there will
    be other failures / alerts and we don't want to spam logs unnecessarily.
    """
    grantees: set[int | str] = set(group_ids)
    if groups_key == "ds_groups":
        try:
            sids = await context.middleware.call(
                "idmap.convert_unixids",
                [{"id_type": "GROUP", "id": x} for x in group_ids],
            )
        except Exception:
            pass
        else:
            grantees |= {s["sid"] for s in sids["mapped"].values()}

    privileges = await context.middleware.call("datastore.query", "account.privilege")
    granted: list[dict[str, Any]] = privileges_group_mapping(privileges, grantees, groups_key)["privileges"]
    return granted


async def roles_for_user(context: ServiceContext, username: str) -> list[str]:
    """
    Return the roles currently granted to `username` by evaluating its
    group membership as reported by NSS.

    Directory services cache entries are not authoritative for privilege
    determination. They carry no group membership, because populating it
    while enumerating the domain would require a group lookup per account
    and overload the domain controller, and so `user.query` reports an
    empty `roles` list for every directory services account. Anything that
    determines privilege must go directly through NSS the way that
    authentication does.
    """
    try:
        user_obj = await context.middleware.call("user.get_user_obj", {"username": username, "get_groups": True})
    except KeyError:
        return []

    privileges = await privileges_for_groups(
        context,
        "local_groups" if user_obj["local"] else "ds_groups",
        # synthetic accounts (container root) have no group list
        user_obj["grouplist"] or [],
    )
    if not privileges:
        return []

    return sorted((await compose_privilege(context, privileges)).roles)
