from __future__ import annotations

from typing import Any, Literal

from truenas_connect_utils.request import auth_headers as _auth_headers
from truenas_connect_utils.request import call as _call

Mode = Literal["get", "post", "put", "delete", "patch", "head"]


def auth_headers(config: dict[str, Any]) -> dict[str, str]:
    return _auth_headers(config)


async def tnc_request(endpoint: str, mode: Mode, **kwargs: Any) -> dict[str, Any]:
    # FIXME: Add network activity check for TNC
    return await _call(endpoint, mode, **kwargs)
