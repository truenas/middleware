from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import B2CredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes
    from middlewared.service_exception import ValidationErrors


class B2RcloneRemote(BaseRcloneRemote[B2CredentialsModel]):
    credentials_schema = B2CredentialsModel

    name = "B2"
    title = "Backblaze B2"

    buckets = True

    fast_list = True

    rclone_type = "b2"

    task_attributes = ["b2_chunk_size"]

    def validate_task_basic(
        self, attributes: CloudTaskAttributes, credentials: B2CredentialsModel, verrors: ValidationErrors,
    ) -> None:
        if not (attributes.b2_chunk_size >= 5):
            verrors.add("chunk_size", "Must be greater than or equal to 5")

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: B2CredentialsModel) -> dict[str, Any]:
        chunk_size = attributes.b2_chunk_size
        extra = {"chunk_size": f"{chunk_size}M"}
        if chunk_size > 200:
            extra["upload_cutoff"] = f"{chunk_size}M"
        return extra

    def get_task_extra_args(self, attributes: CloudTaskAttributes, credentials: B2CredentialsModel) -> list[str]:
        chunk_size = attributes.b2_chunk_size
        if chunk_size > 128:
            return [f"--multi-thread-cutoff={chunk_size * 2 + 1}M"]

        return []
