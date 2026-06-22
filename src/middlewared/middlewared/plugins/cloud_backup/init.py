from __future__ import annotations

import subprocess

from middlewared.api.current import CloudBackupCreate, CloudBackupEntry
from middlewared.plugins.cloud_backup.restic import ResticConfig, get_restic_config
from middlewared.plugins.cloud_backup.utils import resolve_credentials
from middlewared.service import CallError, ServiceContext


class IncorrectPassword(CallError):
    pass


def ensure_initialized(context: ServiceContext, entry: CloudBackupEntry | CloudBackupCreate) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    credentials = resolve_credentials(context, entry.credentials)

    attrs = entry.attributes.model_dump()
    cred = credentials["id"]
    if "bucket" in attrs:
        existing_buckets = [b["Name"] for b in context.middleware.call_sync("cloudsync.list_buckets", cred)]
        if attrs["bucket"] not in existing_buckets:
            context.middleware.call_sync("cloudsync.create_bucket", cred, attrs["bucket"])

    restic_config = get_restic_config(context, entry)

    subprocess.run(
        restic_config.cmd + ["unlock"],
        env=restic_config.env,
        capture_output=True,
        text=True,
    )

    if is_initialized(context, restic_config):
        return

    init(context, entry)


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


def init(context: ServiceContext, entry: CloudBackupEntry | CloudBackupCreate) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    restic_config = get_restic_config(context, entry)

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
