import os

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class GooglePhotosRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_PHOTOS"
    title = "Google Photos"

    rclone_type = "googlephotos"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
    ]
    refresh_credentials = ["token"]

    async def validate_task_full(self, task, credentials, verrors):
        # `/media/by-day` contains a huge tree of empty directories for all days starting from 2000-01-01. Listing
        # them all will never complete due to the API rate limits.

        folder = task["attributes"]["folder"].strip("/")
        if not folder:
            verrors.add(
                "attributes.folder",
                "Pulling from the root directory is not allowed. Please, select a specific directory."
            )
            return

        folder = os.path.normpath(folder)
        for prohibited in ["media", "media/by-day"]:
            if folder == prohibited:
                verrors.add(
                    "attributes.folder",
                    f"Pulling from the {prohibited} directory is not allowed. Please, select a specific directory."
                )
                return
