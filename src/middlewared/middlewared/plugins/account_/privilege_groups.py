from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import wbclient

from middlewared.api.current import GroupEntry, QueryOptions, UnmappedGroupEntry
from middlewared.service_exception import MatchNotFound

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("PrivilegeGroups", "get_groups", "resolve_ds_groups", "resolve_local_groups")


@dataclass(slots=True)
class PrivilegeGroups:
    """Every group the system knows about, indexed the two ways a privilege may reference one."""

    by_gid: dict[int, GroupEntry]
    by_sid: dict[str, GroupEntry]


async def get_groups(context: ServiceContext) -> PrivilegeGroups:
    groups = await context.call2(context.s.group.query)

    return PrivilegeGroups(
        by_gid={group.gid: group for group in groups},
        by_sid={group.sid: group for group in groups if group.sid is not None and not group.local},
    )


def _unmapped_group(*, gid: int | None = None, sid: str | None = None) -> dict[str, Any]:
    return UnmappedGroupEntry(gid=gid, sid=sid, group=None).model_dump()


def resolve_local_groups(
    groups: PrivilegeGroups,
    local_groups: list[int],
    *,
    include_nonexistent: bool = True,
) -> list[dict[str, Any]]:
    result = []
    for gid in local_groups:
        if (group := groups.by_gid.get(gid)) is not None:
            if group.local:
                result.append(group.model_dump())
        elif include_nonexistent:
            result.append(_unmapped_group(gid=gid))

    return result


async def resolve_ds_groups(
    context: ServiceContext,
    groups: PrivilegeGroups,
    ds_groups: list[int | str],
    *,
    include_nonexistent: bool = True,
) -> list[dict[str, Any]]:
    """
    Directory services group privileges may assigned by either GID or SID.
    preference is for latter if it is available. The primary case where it
    will not be available is if this is not active directory.
    """
    result: list[dict[str, Any]] = []

    if sids_to_check := [entry for entry in ds_groups if wbclient.sid_is_valid(str(entry))]:
        try:
            mapped_sids = (await context.middleware.call("idmap.convert_sids", sids_to_check))["mapped"]
        except Exception:
            context.logger.warning("Failed to generate privileges for domain groups", exc_info=True)
            # Report the SIDs as unmapped rather than dropping the whole list, which an update would write back
            mapped_sids = {}
    else:
        mapped_sids = {}

    for xid in ds_groups:
        group: GroupEntry | None
        # -1 stands for "this entry does not name a group that exists", which no group ever matches
        gid = -1
        sid: str | None = None
        if isinstance(xid, int):
            if (group := groups.by_gid.get(xid)) is None:
                gid = xid
        else:
            sid = xid
            if (group := groups.by_sid.get(xid)) is None:
                unixid = mapped_sids.get(xid)
                if unixid is not None and unixid["id_type"] != "USER":
                    gid = unixid["id"]

        if group is None:
            try:
                group = await context.call2(
                    context.s.group.query,
                    [["gid", "=", gid]],
                    QueryOptions(get=True),
                )
            except MatchNotFound:
                if include_nonexistent:
                    result.append(_unmapped_group(gid=gid if gid != -1 else None, sid=sid))

                continue

        if group.local:
            continue

        result.append(group.model_dump())

    return result
