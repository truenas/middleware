from middlewared.rclone.base import BaseRcloneRemote


class GoogleDriveRcloneRemote(BaseRcloneRemote):
    name = "GOOGLE_DRIVE"
    title = "Google Drive"

    fast_list = True

    rclone_type = "drive"

    credentials_oauth = True
    refresh_credentials = ["token"]

    task_attributes = ["acknowledge_abuse"]

    def get_credentials_extra(self, credentials):
        if credentials["provider"].get("team_drive"):
            return dict()

        return dict(root_folder_id="root")
