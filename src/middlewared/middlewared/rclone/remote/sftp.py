import os
import tempfile

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Int, Str


class SFTPRcloneRemote(BaseRcloneRemote):
    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    credentials_schema = [
        Str("host", title="Host", required=True),
        Int("port", title="Port"),
        Str("user", title="Username", required=True),
        Str("pass", title="Password"),
        Int("private_key", title="Private Key ID"),
    ]

    async def get_credentials_extra(self, credentials):
        result = {}

        if "private_key" in credentials["attributes"]:
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_file:
                tmp_file.write((await self.middleware.call("keychaincredential.get_of_type",
                                                           credentials["attributes"]["private_key"],
                                                           "SSH_KEY_PAIR"))["attributes"]["private_key"])

                result["key_file"] = tmp_file.name

        return result

    async def cleanup(self, task, config):
        if "private_key" in task["credentials"]["attributes"]:
            os.unlink(config["key_file"])
