from typing import Any

import requests


def get_microsoft_access_token(client_id: str, client_secret: str, refresh_token: str, scope: str) -> dict[str, Any]:
    r = requests.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "scope": scope,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()  # type: ignore[no-any-return]
