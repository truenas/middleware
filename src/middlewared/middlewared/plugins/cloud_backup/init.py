from __future__ import annotations

import subprocess
from typing import Any

from middlewared.api.current import CloudBackupEntry
from middlewared.plugins.cloud_backup.restic import ResticConfig, get_restic_config
from middlewared.service import CallError, ServiceContext


class IncorrectPassword(CallError):
    pass


# `entry` is typed as a persisted `CloudBackupEntry`, but the create/update validation path passes an
# un-persisted `CloudBackupCreate` (which excludes `id`, `job`, `locked`, ...). Only read fields common to
# both here (`attributes`, `cache_path`, `password`); the credential is supplied separately as `credentials`.
def ensure_initialized(context: ServiceContext, entry: CloudBackupEntry, credentials: dict[str, Any]) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    attrs = entry.attributes.model_dump()
    cred = credentials["id"]
    if "bucket" in attrs:
        existing_buckets = [b["Name"] for b in context.middleware.call_sync("cloudsync.list_buckets", cred)]
        if attrs["bucket"] not in existing_buckets:
            context.middleware.call_sync("cloudsync.create_bucket", cred, attrs["bucket"])

    restic_config = get_restic_config(entry, credentials)

    subprocess.run(
        restic_config.cmd + ["unlock"],
        env=restic_config.env,
        capture_output=True,
        text=True,
    )

    if is_initialized(context, restic_config):
        return

    init(context, entry, credentials)


def is_initialized(context: ServiceContext, restic_config: ResticConfig) -> bool:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    try:
        subprocess.run(
            restic_config.cmd + ["cat", "config"],
            env=restic_config.env,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        text = e.stderr.strip()

        if "Is there a repository at the following location?" in text:
            return False

        if "wrong password or no key found" in text:
            raise IncorrectPassword(text)

        raise CallError(text)


def init(context: ServiceContext, entry: CloudBackupEntry, credentials: dict[str, Any]) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    restic_config = get_restic_config(entry, credentials)

    try:
        subprocess.run(
            restic_config.cmd + ["init"],
            env=restic_config.env,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise CallError(e.stderr)
