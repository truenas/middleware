from typing import Any

from middlewared.api.current import CloudTaskAttributes, CredentialsEntry
from middlewared.rclone.base import BaseRcloneRemote
from middlewared.service_exception import ValidationErrors


class DropboxRcloneRemote(BaseRcloneRemote):
    name = "DROPBOX"
    title = "Dropbox"

    rclone_type = "dropbox"

    credentials_oauth = True

    task_attributes = ["dropbox_chunk_size"]

    def validate_task_basic(
        self, attributes: CloudTaskAttributes, credentials: CredentialsEntry, verrors: ValidationErrors,
    ) -> None:
        attrs = attributes.model_dump(by_alias=True)

        if not (attrs["chunk_size"] >= 5):
            verrors.add("chunk_size", "Must be greater than or equal to 5")

        if not (attrs["chunk_size"] < 150):
            verrors.add("chunk_size", "Must be less than 5")

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: CredentialsEntry) -> dict[str, Any]:
        return {"chunk_size": str(attributes.model_dump(by_alias=True).get("chunk_size", 48)) + "M"}
