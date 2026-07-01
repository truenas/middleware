from __future__ import annotations

import os
from typing import Any

import aiohttp

from middlewared.utils import ajson

USAGE_URL = "https://usage.truenas.com/submit"


async def submit_stats(data: dict[str, Any]) -> None:
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        await session.post(
            USAGE_URL,
            data=await ajson.dumps(data, sort_keys=True),
            headers={"Content-type": "application/json"},
            proxy=os.environ.get("http_proxy"),
        )
