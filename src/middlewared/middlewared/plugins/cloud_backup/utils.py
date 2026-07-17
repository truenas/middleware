from __future__ import annotations

from typing import Any

from middlewared.api.current import CredentialsEntry
from middlewared.service import ServiceContext


# FIXME: Remove once the cloud_sync plugin is converted; its dict-based restic/rclone layer is why we marshal here.
def resolve_credentials(context: ServiceContext, credentials: int | CredentialsEntry) -> dict[str, Any]:
    """Return the cloud credential as the flat, plaintext provider dict the restic/rclone helpers consume.

    This is the single place that turns a credential reference into that dict, and each operation calls
    it once and threads the result down. The reference is an ``int`` id on a create/update payload or a
    ``CredentialsEntry`` on a persisted task; either way it points at an existing ``system.cloudcredentials``
    row. We dump the fetched entry with ``expose_secrets`` (secrets revealed, not masked) and ``by_alias``
    (provider-specific aliases such as ``pass``) so the restic/rclone layer receives the exact plaintext
    shape it was stored with, which flows into the ``CLOUD_BACKUP_*`` script env.
    """
    cred_id = credentials if isinstance(credentials, int) else credentials.id
    entry = context.call_sync2(context.s.cloudsync.credentials.get_instance, cred_id)
    return entry.model_dump(by_alias=True, context={"expose_secrets": True})
