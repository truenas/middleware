from middlewared.api import api_method
from middlewared.api.current import CloudSyncOneDriveListDrivesArgs, CloudSyncOneDriveListDrivesResult
from middlewared.rclone.base import BaseRcloneRemote


class OneDriveRcloneRemote(BaseRcloneRemote):
    name = "ONEDRIVE"
    title = "Microsoft OneDrive"

    fast_list = True

    rclone_type = "onedrive"

    credentials_oauth = True
    refresh_credentials = ["token"]

    extra_methods = ["list_drives"]

    @api_method(CloudSyncOneDriveListDrivesArgs, CloudSyncOneDriveListDrivesResult)
    async def list_drives(self, credentials):
        return ["This", "works."]
