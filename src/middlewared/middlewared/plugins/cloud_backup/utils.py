from __future__ import annotations

from middlewared.api.current import CredentialsEntry
from middlewared.service import ServiceContext


def resolve_credentials(context: ServiceContext, credentials: int | CredentialsEntry) -> CredentialsEntry:
    """Return the cloud credential (with plaintext secrets) for a task's credential reference.

    The reference is an ``int`` id on a create/update payload or an already-resolved ``CredentialsEntry`` on a
    persisted task; either way it points at an existing ``system.cloudcredentials`` row.
    """
    if isinstance(credentials, CredentialsEntry):
        return credentials
    return context.call_sync2(context.s.cloudsync.credentials.get_instance, credentials)
