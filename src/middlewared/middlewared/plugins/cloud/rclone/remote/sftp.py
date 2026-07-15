from __future__ import annotations

import os
import tempfile
from typing import Any

from middlewared.api.current import SFTPCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class SFTPRcloneRemote(BaseRcloneRemote[SFTPCredentialsModel]):
    credentials_schema = SFTPCredentialsModel

    name = "SFTP"
    title = "SFTP"

    rclone_type = "sftp"

    def get_credentials_extra(self, credentials: SFTPCredentialsModel) -> dict[str, Any]:
        result: dict[str, Any] = {}

        if (private_key := credentials.private_key.get_secret_value()) is not None:
            key_pair = self.middleware.call_sync2(
                self.middleware.services.keychaincredential.get_of_type,
                private_key,
                "SSH_KEY_PAIR",
            )
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_file:
                tmp_file.write(key_pair.attributes.get_secret_value().private_key or "")

                result["key_file"] = tmp_file.name

        return result

    def cleanup(self, credentials: SFTPCredentialsModel, config: dict[str, Any]) -> None:
        if credentials.private_key.get_secret_value() is not None:
            os.unlink(config["key_file"])
