from __future__ import annotations

import errno
from typing import TYPE_CHECKING

from middlewared.api.current import QueryOptions
from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

BUILTIN_GIDS: dict[str, int] = {}


async def get_builtin_group_id(context: ServiceContext, group_name: str) -> int:
    if not BUILTIN_GIDS:
        BUILTIN_GIDS.update(
            {
                group.group: group.gid
                for group in await context.call2(
                    context.s.group.query,
                    [["builtin", "=", True]],
                    QueryOptions(force_sql_filters=True),
                )
            }
        )

    try:
        return BUILTIN_GIDS[group_name]
    except KeyError:
        raise CallError(f"{group_name!r} group not found", errno.ENOENT)
