from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from middlewared.api.current import CredentialsVerifyData
from middlewared.plugins.cloud_sync import RcloneConfig, lsjson_error_excerpt
from middlewared.rclone.remote.s3_providers import S3_PROVIDERS

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel

    from . import CredentialsService


def verify(service: CredentialsService, provider: BaseModel) -> CredentialsVerifyData:
    attributes = provider.model_dump(by_alias=True, context={"expose_secrets": True}, warnings=False)

    service.middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

    with RcloneConfig({"credentials": {"provider": attributes}}) as config:  # type: ignore[no-untyped-call]
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
