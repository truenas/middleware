from __future__ import annotations

from typing import Any

from middlewared.api.current import CredentialsEntry
from middlewared.service import ServiceContext


def resolve_credentials(context: ServiceContext, credentials: int | CredentialsEntry) -> dict[str, Any]:
    """Return the cloud credential record (with the flat, revealed provider dict restic needs).

    The credential id may come straight from a create/update payload (``int``) or from a persisted
    entry (``CredentialsEntry``). Either way the provider secrets are owned by the unconverted
    ``cloudsync.credentials`` service, which is the only source of the flat ``provider`` dict shape
    the restic helpers consume.
    """
    cred_id = credentials if isinstance(credentials, int) else credentials.id
    record: dict[str, Any] = context.middleware.call_sync("cloudsync.credentials.get_instance", cred_id)
    return record
