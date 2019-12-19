import textwrap

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Int, Str
from middlewared.validators import Range


class DropboxRcloneRemote(BaseRcloneRemote):
    name = "DROPBOX"
    title = "Dropbox"

    rclone_type = "dropbox"

    credentials_schema = [
        Str("client_id", title="OAuth Client ID", default=""),
        Str("client_secret", title="OAuth Client Secret", default=""),
        Str("token", title="Access Token", required=True, max_length=None),
    ]
    credentials_oauth = True

    task_schema = [
        Int("chunk_size", title="Upload chunk size (in megabytes)", description=textwrap.dedent("""\
            Upload chunk size. Must fit in memory. Note that these chunks are buffered in memory and there might be a
            maximum of «--transfers» chunks in progress at once. Dropbox Business accounts can have monthly data
            transfer limits per team per month. By using larger chnuk sizes you will decrease the number of data
            transfer calls used and you'll be able to transfer more data to your Dropbox Business account.
        """), default=48, validators=[Range(min=5, max=149)]),
    ]

    async def get_task_extra(self, task):
        return {"chunk_size": str(task["attributes"].get("chunk_size", 48)) + "M"}
