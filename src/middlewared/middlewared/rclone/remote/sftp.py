import os
import tempfile
from typing import Any

from middlewared.api.current import CredentialsEntry
from middlewared.rclone.base import BaseRcloneRemote


class SFTPRcloneRemote(BaseRcloneRemote):
    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    def get_credentials_extra(self, credentials: CredentialsEntry) -> dict[str, Any]:
        provider = self._provider_config(credentials)

        result: dict[str, Any] = {}

        if provider.get("private_key") is not None:
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_file:
                tmp_file.write(
                    self.middleware.call_sync2(
                        self.middleware.services.keychaincredential.get_of_type,
                        provider["private_key"],
                        "SSH_KEY_PAIR"
                    ).attributes.get_secret_value().private_key
                )

                result["key_file"] = tmp_file.name

        return result

    def cleanup(self, credentials: CredentialsEntry, config: dict[str, Any]) -> None:
        provider = self._provider_config(credentials)
        if provider.get("private_key") is not None:
            os.unlink(config["key_file"])
