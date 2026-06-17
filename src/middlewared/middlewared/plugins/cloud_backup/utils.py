from __future__ import annotations

from typing import Any

from middlewared.api.current import CloudBackupEntry
from middlewared.service import ServiceContext


def revealed_dict(context: ServiceContext, entry: CloudBackupEntry) -> dict[str, Any]:
    """Return a cloud backup entry as a plain dict with the secrets restic needs revealed.

    ``model_dump`` redacts the ``Secret`` password, and the credential's provider secrets are
    only available as a plain dict from the (unconverted) ``cloudsync`` service. The restic
    helpers consume this dict shape directly.
    """
    data = entry.model_dump(context={"expose_secrets": True})
    data["credentials"] = context.middleware.call_sync(
        "cloudsync.credentials.get_instance",
        entry.credentials.id,
    )
    return data
