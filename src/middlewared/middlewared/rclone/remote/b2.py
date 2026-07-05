from typing import Any

from middlewared.api.current import CloudTaskAttributes, CredentialsEntry
from middlewared.rclone.base import BaseRcloneRemote
from middlewared.service_exception import ValidationErrors


class B2RcloneRemote(BaseRcloneRemote):
    name = "B2"
    title = "Backblaze B2"

    buckets = True

    fast_list = True

    rclone_type = "b2"

    task_attributes = ["b2_chunk_size"]

    def validate_task_basic(
        self, attributes: CloudTaskAttributes, credentials: CredentialsEntry, verrors: ValidationErrors,
    ) -> None:
        attrs = attributes.model_dump(by_alias=True)
        if not (attrs["chunk_size"] >= 5):
            verrors.add("chunk_size", "Must be greater than or equal to 5")

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: CredentialsEntry) -> dict[str, Any]:
        chunk_size = attributes.model_dump(by_alias=True).get("chunk_size", 96)
        extra = {"chunk_size": f"{chunk_size}M"}
        if chunk_size > 200:
            extra["upload_cutoff"] = f"{chunk_size}M"
        return extra

    def get_task_extra_args(self, attributes: CloudTaskAttributes) -> list[str]:
        chunk_size = attributes.model_dump(by_alias=True).get("chunk_size", 96)
        if chunk_size > 128:
            return [f"--multi-thread-cutoff={chunk_size * 2 + 1}M"]

        return []
