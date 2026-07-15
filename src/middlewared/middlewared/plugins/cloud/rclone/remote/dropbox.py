from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import DropboxCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes
    from middlewared.service_exception import ValidationErrors


class DropboxRcloneRemote(BaseRcloneRemote[DropboxCredentialsModel]):
    credentials_schema = DropboxCredentialsModel

    name = "DROPBOX"
    title = "Dropbox"

    rclone_type = "dropbox"

    credentials_oauth = True

    task_attributes = ["dropbox_chunk_size"]

    def validate_task_basic(
        self, attributes: CloudTaskAttributes, credentials: DropboxCredentialsModel, verrors: ValidationErrors,
    ) -> None:
        if not (attributes.dropbox_chunk_size >= 5):
            verrors.add("chunk_size", "Must be greater than or equal to 5")

        if not (attributes.dropbox_chunk_size < 150):
            verrors.add("chunk_size", "Must be less than 5")

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: DropboxCredentialsModel) -> dict[str, Any]:
        return {"chunk_size": str(attributes.dropbox_chunk_size) + "M"}
