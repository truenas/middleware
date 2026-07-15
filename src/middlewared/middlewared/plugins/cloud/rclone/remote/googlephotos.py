from __future__ import annotations

import os
from typing import TYPE_CHECKING

from middlewared.api.current import GooglePhotosCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes
    from middlewared.service_exception import ValidationErrors


class GooglePhotosRcloneRemote(BaseRcloneRemote[GooglePhotosCredentialsModel]):
    credentials_schema = GooglePhotosCredentialsModel

    name = "GOOGLE_PHOTOS"
    title = "Google Photos"

    rclone_type = "googlephotos"

    refresh_credentials = ["token"]

    def validate_task_full(
        self,
        attributes: CloudTaskAttributes,
        credentials: GooglePhotosCredentialsModel,
        verrors: ValidationErrors,
    ) -> None:
        # `/media/by-day` contains a huge tree of empty directories for all days starting from 2000-01-01. Listing
        # them all will never complete due to the API rate limits.

        folder = attributes.folder.strip("/")
        if not folder:
            verrors.add(
                "attributes.folder",
                "Pulling from the root directory is not allowed. Please, select a specific directory.",
            )
            return

        folder = os.path.normpath(folder)
        for prohibited in ["media", "media/by-day"]:
            if folder == prohibited:
                verrors.add(
                    "attributes.folder",
                    f"Pulling from the {prohibited} directory is not allowed. Please, select a specific directory.",
                )
                return
