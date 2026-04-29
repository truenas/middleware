from __future__ import annotations

from middlewared.service import ServiceContext

from .utils import get_app_stop_cache_key


async def process_event(context: ServiceContext, app_name: str) -> None:
    cache_key = get_app_stop_cache_key(app_name)
    if (app := await context.call2(context.s.app.query, [["id", "=", app_name]])) and not await context.middleware.call(
        "cache.has_key", cache_key
    ):
        context.middleware.send_event(
            "app.query", "CHANGED", id=app_name, fields=app[0].model_dump(by_alias=True),
        )
