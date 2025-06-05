from middlewared.rclone.base import BaseRcloneRemote


class DropboxRcloneRemote(BaseRcloneRemote):
    name = "DROPBOX"
    title = "Dropbox"

    rclone_type = "dropbox"

    credentials_oauth = True

    task_attributes = ["dropbox_chunk_size"]

    async def get_task_extra(self, task):
        return {"chunk_size": str(task["attributes"].get("chunk_size", 48)) + "M"}
