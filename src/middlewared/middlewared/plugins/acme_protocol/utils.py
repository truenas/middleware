from __future__ import annotations

from typing import Any

from truenas_acme_utils.client_utils import get_acme_client_and_key as _get_client_and_key

from middlewared.service import ServiceContext


def get_acme_client_and_key_payload(
    context: ServiceContext, acme_directory_uri: str, tos: bool = False,
) -> dict[str, Any]:
    data: list[dict[str, Any]] = context.middleware.call_sync(
        'acme.registration.query', [['directory', '=', acme_directory_uri]]
    )
    if not data:
        result: dict[str, Any] = context.middleware.call_sync(
            'acme.registration.create',
            {'tos': tos, 'acme_directory_uri': acme_directory_uri},
        )
        return result
    return data[0]


def get_acme_client_and_key(
    context: ServiceContext, acme_directory_uri: str, tos: bool = False,
) -> tuple[Any, Any]:
    result: tuple[Any, Any] = _get_client_and_key(
        get_acme_client_and_key_payload(context, acme_directory_uri, tos)
    )
    return result
