from __future__ import annotations

from typing import Any, cast

from truenas_acme_utils.client_utils import ACMEClientAndKeyData, get_acme_client_and_key as _get_client_and_key

from middlewared.plugins.acme_registration.models import ACMERegistrationCreate
from middlewared.service import ServiceContext


def get_acme_client_and_key_payload(
    context: ServiceContext, acme_directory_uri: str, tos: bool = False,
) -> ACMEClientAndKeyData:
    data = context.call_sync2(
        context.s.acme.registration.query, [['directory', '=', acme_directory_uri]]
    )
    if not data:
        entry = context.call_sync2(
            context.s.acme.registration.create,
            ACMERegistrationCreate(tos=tos, acme_directory_uri=acme_directory_uri),
        )
        payload = cast(ACMEClientAndKeyData, entry.model_dump())
    else:
        payload = cast(ACMEClientAndKeyData, data[0].model_dump())
    return payload


def get_acme_client_and_key(
    context: ServiceContext, acme_directory_uri: str, tos: bool = False,
) -> tuple[Any, Any]:
    return _get_client_and_key(
        get_acme_client_and_key_payload(context, acme_directory_uri, tos)
    )
