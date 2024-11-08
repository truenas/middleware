import os
import tempfile

from middlewared.rclone.base import BaseRcloneRemote


class SFTPRcloneRemote(BaseRcloneRemote):
    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    async def get_credentials_extra(self, credentials):
        result = {}

        if "private_key" in credentials["provider"]:
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_file:
                tmp_file.write((await self.middleware.call("keychaincredential.get_of_type",
                                                           credentials["provider"]["private_key"],
                                                           "SSH_KEY_PAIR"))["provider"]["private_key"])

                result["key_file"] = tmp_file.name

        return result

    async def cleanup(self, task, config):
        if "private_key" in task["credentials"]["provider"]:
            os.unlink(config["key_file"])
