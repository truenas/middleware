from middlewared.rclone.base import BaseRcloneRemote


class DropboxRcloneRemote(BaseRcloneRemote):
    name = "DROPBOX"
    title = "Dropbox"

    rclone_type = "dropbox"

    credentials_oauth = True

    task_attributes = ["dropbox_chunk_size"]

    async def validate_task_basic(self, task, credentials, verrors):
        if not (task["attributes"]["chunk_size"] >= 5):
            verrors.add("chunk_size", "Must be greater than or equal to 5")

        if not (task["attributes"]["chunk_size"] < 150):
            verrors.add("chunk_size", "Must be less than 5")

    async def get_task_extra(self, task):
        return {"chunk_size": str(task["attributes"].get("chunk_size", 48)) + "M"}
