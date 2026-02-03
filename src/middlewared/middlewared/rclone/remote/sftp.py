import os
import tempfile

from middlewared.rclone.base import BaseRcloneRemote


class SFTPRcloneRemote(BaseRcloneRemote):
    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    def get_credentials_extra(self, credentials):
        result = {}

        if credentials["provider"].get("private_key") is not None:
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_file:
                tmp_file.write(
                    self.middleware.call_sync(
                        "keychaincredential.get_of_type",
                        credentials["provider"]["private_key"],
                        "SSH_KEY_PAIR"
                    )["attributes"]["private_key"]
                )

                result["key_file"] = tmp_file.name

        return result

    def cleanup(self, task, config):
        if task["credentials"]["provider"].get("private_key") is not None:
            os.unlink(config["key_file"])
