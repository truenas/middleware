"""Grant lists, shared by buckets and the service's global grants."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.service import ValidationErrors

if TYPE_CHECKING:
    from middlewared.main import Middleware


async def resolve_grant_names(middleware: Middleware, grants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach the current user or group name to each grant for display.
    The daemon never matches on it; the xid is the identity. A principal
    that no longer resolves keeps its xid as the name."""
    out = []
    for grant in grants:
        name = ""
        if grant["principal_type"] == "USER":
            try:
                name = (await middleware.call("user.get_user_obj", {"uid": grant["xid"]}))["pw_name"]
            except KeyError:
                name = str(grant["xid"])
        elif grant["principal_type"] == "GROUP":
            try:
                name = (await middleware.call("group.get_group_obj", {"gid": grant["xid"]}))["gr_name"]
            except KeyError:
                name = str(grant["xid"])
        out.append({**grant, "name": name})
    return out


async def validate_grants(middleware: Middleware, schema: str, grants: list[Any], verrors: ValidationErrors) -> None:
    seen: set[tuple[str, int | None]] = set()
    for i, grant in enumerate(grants):
        principal_type, xid = grant.principal_type, grant.xid
        if principal_type == "EVERYONE":
            if xid is not None:
                verrors.add(f"{schema}.{i}.xid", "xid is not allowed for an EVERYONE grant.")
        elif xid is None:
            verrors.add(f"{schema}.{i}.xid", f"xid is required for a {principal_type} grant.")
        elif principal_type == "USER":
            try:
                await middleware.call("user.get_user_obj", {"uid": xid})
            except KeyError:
                verrors.add(f"{schema}.{i}.xid", f"No user with uid {xid} exists.")
        else:
            try:
                await middleware.call("group.get_group_obj", {"gid": xid})
            except KeyError:
                verrors.add(f"{schema}.{i}.xid", f"No group with gid {xid} exists.")

        key = (principal_type, xid)
        if key in seen:
            verrors.add(f"{schema}.{i}", "The same principal may only be granted once.")
        seen.add(key)
