from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.api.current import CloudTaskAttributes
    from middlewared.main import Middleware
    from middlewared.service_exception import ValidationErrors


class BaseRcloneRemote[CredentialsT: BaseModel]:
    credentials_schema: type[CredentialsT]

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

    restic = False

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware

    def create_bucket(self, credentials: CredentialsT, name: str) -> None:
        raise NotImplementedError

    def list_buckets(self, credentials: CredentialsT) -> list[Any]:
        raise NotImplementedError

    def validate_task_basic(
        self,
        attributes: CloudTaskAttributes,
        credentials: CredentialsT,
        verrors: ValidationErrors,
    ) -> None:
        pass

    def validate_task_full(
        self,
        attributes: CloudTaskAttributes,
        credentials: CredentialsT,
        verrors: ValidationErrors,
    ) -> None:
        pass

    def get_credentials_extra(self, credentials: CredentialsT) -> dict[str, Any]:
        return {}

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: CredentialsT) -> dict[str, Any]:
        return {}

    def get_task_extra_args(self, attributes: CloudTaskAttributes, credentials: CredentialsT) -> list[str]:
        return []

    def cleanup(self, credentials: CredentialsT, config: dict[str, Any]) -> None:
        pass

    def get_restic_config(
        self,
        attributes: CloudTaskAttributes,
        credentials: CredentialsT,
    ) -> tuple[str, dict[str, str]]:
        raise NotImplementedError
