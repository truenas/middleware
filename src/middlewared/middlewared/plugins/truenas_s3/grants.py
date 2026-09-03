"""Grant lists, shared by buckets and the service's global grants."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.service import ValidationErrors

if TYPE_CHECKING:
    from middlewared.main import Middleware


async def principal_names(middleware: Middleware, uids: set[int], gids: set[int]) -> dict[str, dict[int, str]]:
    """The current name of each uid and gid, resolved once each through
    NSS, which is what the daemon will resolve them through too. An id
    that does not resolve is left out; readers fall back to the id."""
    users: dict[int, str] = {}
    for uid in uids:
        try:
            users[uid] = (await middleware.call("user.get_user_obj", {"uid": uid}))["pw_name"]
        except KeyError:
            pass
    groups: dict[int, str] = {}
    for gid in gids:
        try:
            groups[gid] = (await middleware.call("group.get_group_obj", {"gid": gid}))["gr_name"]
        except KeyError:
            pass
    return {"users": users, "groups": groups}


def grant_principals(grants: list[dict[str, Any]]) -> tuple[set[int], set[int]]:
    """The uids and gids a grant list names."""
    uids = {g["xid"] for g in grants if g["principal_type"] == "USER"}
    gids = {g["xid"] for g in grants if g["principal_type"] == "GROUP"}
    return uids, gids


def grant_label(name: str | None, xid: int | None) -> str:
    """The quoted NAME of a rendered grant heading. A label the daemon never
    resolves, but a quote inside it breaks the heading grammar and an empty
    one is refused, either of which refuses the whole load."""
    label = (name or "").replace('"', "").replace("\n", "").replace("\r", "").strip()
    return label or str(xid)


def label_grants(grants: list[dict[str, Any]], names: dict[str, dict[int, str]]) -> list[dict[str, Any]]:
    """Attach the current user or group name to each grant for display.
    The daemon never matches on it; the xid is the identity. A principal
    that no longer resolves keeps its xid as the name."""
    out = []
    for grant in grants:
        name = ""
        if grant["principal_type"] == "USER":
            name = names["users"].get(grant["xid"], str(grant["xid"]))
        elif grant["principal_type"] == "GROUP":
            name = names["groups"].get(grant["xid"], str(grant["xid"]))
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
