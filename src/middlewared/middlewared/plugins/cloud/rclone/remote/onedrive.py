import json
from typing import TYPE_CHECKING, Any

import requests

from middlewared.api import api_method
from middlewared.api.current import (
    CloudSyncOneDriveListDrivesArgs,
    CloudSyncOneDriveListDrivesDrive,
    CloudSyncOneDriveListDrivesResult,
    OneDriveCredentialsModel,
)
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote
from middlewared.utils.microsoft import get_microsoft_access_token

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes

DRIVES_TYPES = {
    "PERSONAL": "personal",
    "BUSINESS": "business",
    "DOCUMENT_LIBRARY": "documentLibrary",
}
DRIVES_TYPES_INV = {v: k for k, v in DRIVES_TYPES.items()}


class OneDriveRcloneRemote(BaseRcloneRemote[OneDriveCredentialsModel]):
    credentials_schema = OneDriveCredentialsModel

    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    rclone_type = "onedrive"

    credentials_oauth = True
    refresh_credentials = ["token"]

    extra_methods = ["list_drives"]

    def get_task_extra(
        self, attributes: "CloudTaskAttributes", credentials: OneDriveCredentialsModel,
    ) -> dict[str, Any]:
        return {
            "drive_type": DRIVES_TYPES.get(credentials.drive_type.get_secret_value(), ""),
            # Subject to change as Microsoft changes rate limits; please watch `forum.rclone.org`
            "checkers": "1",
            "tpslimit": "10",
        }

    @api_method(CloudSyncOneDriveListDrivesArgs, CloudSyncOneDriveListDrivesResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    def list_drives(self, credentials: CloudSyncOneDriveListDrivesArgs) -> list[CloudSyncOneDriveListDrivesDrive]:
        """
        Lists all available drives and their types for given Microsoft OneDrive credentials.
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

        client_id = credentials.client_id.get_secret_value() or "b15665d9-eda6-4092-8539-0eec376afd59"
        client_secret = credentials.client_secret.get_secret_value() or "qtyfaBBYA403=unZUP40~_#"

        token = json.loads(credentials.token.get_secret_value())

        r = requests.get(
            "https://graph.microsoft.com/v1.0/me/drives",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=10,
        )
        if r.status_code == 401:
            token = get_microsoft_access_token(
                client_id,
                client_secret,
                token["refresh_token"],
                "Files.Read Files.ReadWrite Files.Read.All Files.ReadWrite.All Sites.Read.All offline_access",
            )
            r = requests.get(
                "https://graph.microsoft.com/v1.0/me/drives",
                headers={"Authorization": f"Bearer {token['access_token']}"},
                timeout=10,
            )
        r.raise_for_status()

        def process_drive(drive: dict[str, Any]) -> CloudSyncOneDriveListDrivesDrive:
            return CloudSyncOneDriveListDrivesDrive(
                drive_type=DRIVES_TYPES_INV.get(drive["driveType"], ""),  # type: ignore[arg-type]
                drive_id=drive["id"],
                name=drive.get("name") or "",
                description=drive.get("description") or "",
            )

        result = []
        for drive in r.json()["value"]:
            result.append(process_drive(drive))
        # Also call /me/drive as sometimes /me/drives doesn't return it
        # see https://github.com/rclone/rclone/issues/4068
        r = requests.get(
            "https://graph.microsoft.com/v1.0/me/drive",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=10,
        )
        r.raise_for_status()
        me_drive = process_drive(r.json())
        if me_drive not in result:
            result.insert(0, me_drive)
        return result
