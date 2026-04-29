from __future__ import annotations

import base64
from typing import Any

from middlewared.api.current import AppRegistryEntry


def generate_docker_auth_config(auth_list: list[AppRegistryEntry]) -> dict[str, Any]:
    auths: dict[str, dict[str, str]] = {}
    for auth in auth_list:
        creds = f"{auth.username.get_secret_value()}:{auth.password.get_secret_value()}"
        auths[auth.uri] = {
            # Encode username:password in base64
            "auth": base64.b64encode(creds.encode()).decode(),
        }

    return {
        "auths": auths,
    }
