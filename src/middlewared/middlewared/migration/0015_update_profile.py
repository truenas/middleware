from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    # Previously force-set `update.profile = MISSION_CRITICAL` on enterprise systems.
    # That overrode the running version's actual profile (e.g., a system upgrading
    # from Fangtooth to a Goldeye EARLY_ADOPTER release ended up flagged as out of
    # profile once a MISSION_CRITICAL Goldeye release was published). Leave the
    # profile null instead — `update.config` auto-populates it from
    # `current_version_profile()` on first read.
    pass
