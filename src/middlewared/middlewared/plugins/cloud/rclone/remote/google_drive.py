from __future__ import annotations

from typing import Any

from middlewared.api.current import GoogleDriveCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class GoogleDriveRcloneRemote(BaseRcloneRemote[GoogleDriveCredentialsModel]):
    credentials_schema = GoogleDriveCredentialsModel

    name = "GOOGLE_DRIVE"
    title = "Google Drive"

    fast_list = True

    rclone_type = "drive"

    credentials_oauth = True
    refresh_credentials = ["token"]

    task_attributes = ["acknowledge_abuse"]

    def get_credentials_extra(self, credentials: GoogleDriveCredentialsModel) -> dict[str, Any]:
        if credentials.team_drive.get_secret_value():
            return dict()

        return dict(root_folder_id="root")
