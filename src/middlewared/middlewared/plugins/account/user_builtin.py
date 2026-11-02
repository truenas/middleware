from __future__ import annotations

import errno
from typing import TYPE_CHECKING

from middlewared.api.current import QueryOptions
from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("get_builtin_user_id",)

BUILTIN_UIDS: dict[str, int] = {}


async def get_builtin_user_id(context: ServiceContext, username: str) -> int:
    if not BUILTIN_UIDS:
        BUILTIN_UIDS.update(
            {
                user.username: user.uid
                for user in await context.call2(
                    context.s.user.query,
                    [["builtin", "=", True]],
                    QueryOptions(force_sql_filters=True),
                )
            }
        )

    try:
        return BUILTIN_UIDS[username]
    except KeyError:
        raise CallError(f"{username!r} user not found", errno.ENOENT)
