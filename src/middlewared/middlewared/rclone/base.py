from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import CloudTaskAttributes, CredentialsEntry
from middlewared.service_exception import ValidationErrors

if TYPE_CHECKING:
    from middlewared.main import Middleware


def expose_provider_config(credentials: CredentialsEntry) -> dict[str, Any]:
    """Return the flat, plaintext provider dict the rclone/restic config is built from.

    Uses ``mode="python"`` because ``mode="json"`` does **not** honor the ``expose_secrets`` context
    (it masks every ``Secret[...]`` field with the redaction string); we stringify the remaining
    non-primitive values (e.g. ``HttpUrl`` endpoints) ourselves so the result is config-file friendly.

    ``None`` values are dropped so unset optional fields (e.g. an SFTP ``pass`` on a key-based
    credential) never reach rclone/restic, which would otherwise choke on them.
    """
    result: dict[str, Any] = {}
    dumped = credentials.provider.model_dump(
        by_alias=True, context={"expose_secrets": True}, exclude_none=True, warnings=False,
    )
    for k, v in dumped.items():
        if isinstance(v, (str, int, float, bool)):
            result[k] = v
        else:
            result[k] = str(v)
    return result


class BaseRcloneRemote:
    name: str
    title: str
    rclone_type: str

    buckets = False
    bucket_title = "Bucket"
    can_create_bucket = False
    custom_list_buckets = False

    readonly = False

    fast_list = False

    credentials_oauth = False
    credentials_oauth_name: str | None = None
    refresh_credentials: list[str] = []

    task_attributes: list[str] = []

    extra_methods: list[str] = []

    def __init__(self, middleware: Middleware):
        self.middleware = middleware

    @staticmethod
    def _provider_config(credentials: CredentialsEntry) -> dict[str, Any]:
        """Return the flat, plaintext provider dict (secrets exposed, URLs/aliases as stored)."""
        return expose_provider_config(credentials)

    def create_bucket(self, credentials: CredentialsEntry, name: str) -> None:
        raise NotImplementedError

    def list_buckets(self, credentials: CredentialsEntry) -> list[dict[str, Any]]:
        raise NotImplementedError

    def validate_task_basic(
        self, attributes: CloudTaskAttributes, credentials: CredentialsEntry, verrors: ValidationErrors,
    ) -> None:
        pass

    def validate_task_full(
        self, attributes: CloudTaskAttributes, credentials: CredentialsEntry, verrors: ValidationErrors,
    ) -> None:
        pass

    def get_credentials_extra(self, credentials: CredentialsEntry) -> dict[str, Any]:
        return {}

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: CredentialsEntry) -> dict[str, Any]:
        return {}

    def get_task_extra_args(self, attributes: CloudTaskAttributes) -> list[str]:
        return []

    def cleanup(self, credentials: CredentialsEntry, config: dict[str, Any]) -> None:
        pass

    def get_restic_config(
        self, credentials: CredentialsEntry, attributes: CloudTaskAttributes,
    ) -> tuple[str, dict[str, str]]:
        raise NotImplementedError
