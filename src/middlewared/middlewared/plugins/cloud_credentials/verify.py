from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from middlewared.api.current import CredentialsVerifyData
from middlewared.plugins.cloud.rclone.remote.s3_providers import S3_PROVIDERS
from middlewared.plugins.cloud_sync.rclone import RcloneConfig, lsjson_error_excerpt

if TYPE_CHECKING:
    from middlewared.api.current import (
        CloudCredentialProvider,
    )

    from . import CredentialsService


def verify(service: CredentialsService, provider: CloudCredentialProvider) -> CredentialsVerifyData:
    service.middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

    # No task, just the provider credential to validate.
    with RcloneConfig(provider) as config:
        proc = subprocess.run(
            ["rclone", "--config", config.config_path, "--contimeout", "15s", "--timeout", "30s", "lsjson", "remote:"],
            check=False,
            encoding="utf8",
            capture_output=True,
        )
        if proc.returncode == 0:
            return CredentialsVerifyData(valid=True)
        else:
            return CredentialsVerifyData(valid=False, error=proc.stderr, excerpt=lsjson_error_excerpt(proc.stderr))


def s3_provider_choices() -> dict[str, str]:
    return S3_PROVIDERS
