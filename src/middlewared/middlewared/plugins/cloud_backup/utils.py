from __future__ import annotations

from typing import Any

from middlewared.api.current import CredentialsEntry
from middlewared.service import ServiceContext


# FIXME: Remove once the cloud_sync plugin is converted; its dict-based rclone layer is why we marshal here.
def resolve_credentials(context: ServiceContext, credentials: int | CredentialsEntry) -> dict[str, Any]:
    """Return the cloud credential as the flat, plaintext provider dict the restic/rclone helpers consume.

    This is the single place that turns a credential reference into that dict, and each operation calls
    it once and threads the result down. The reference is an ``int`` id on a create/update payload or a
    ``CredentialsEntry`` on a persisted task; either way it points at an existing ``system.cloudcredentials``
    row, so we fetch it from the unconverted ``cloudsync.credentials`` service. We deliberately do not dump
    the entry's ``CredentialsEntry`` instead: its secrets are masked, and ``model_dump`` drifts from the
    stored shape (URL normalization, default-filled keys) that flows into the ``CLOUD_BACKUP_*`` script env.
    """
    cred_id = credentials if isinstance(credentials, int) else credentials.id
    record: dict[str, Any] = context.middleware.call_sync("cloudsync.credentials.get_instance", cred_id)
    return record
