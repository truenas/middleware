from __future__ import annotations

from datetime import datetime
import json
import subprocess
from typing import TYPE_CHECKING

from middlewared.api.current import CloudBackupSnapshot, CloudBackupSnapshotItem
from middlewared.plugins.cloud_backup.restic import get_restic_config
from middlewared.plugins.cloud_backup.utils import resolve_credentials
from middlewared.service import CallError, ServiceContext

if TYPE_CHECKING:
    from middlewared.job import Job


def list_snapshots(context: ServiceContext, id_: int) -> list[CloudBackupSnapshot]:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    entry = context.call_sync2(context.s.cloud_backup.get_instance, id_)

    credentials = resolve_credentials(context, entry.credentials)
    restic_config = get_restic_config(entry, credentials)

    try:
        snapshots = json.loads(subprocess.run(
            restic_config.cmd + ["--json", "snapshots"],
            env=restic_config.env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout)
    except subprocess.CalledProcessError as e:
        raise CallError(e.stderr)

    for snapshot in snapshots:
        snapshot["time"] = datetime.fromisoformat(snapshot["time"])

    return [CloudBackupSnapshot(**snapshot) for snapshot in snapshots]


def list_snapshot_directory(
    context: ServiceContext, id_: int, snapshot_id: str, path: str,
) -> list[CloudBackupSnapshotItem]:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    entry = context.call_sync2(context.s.cloud_backup.get_instance, id_)

    credentials = resolve_credentials(context, entry.credentials)
    restic_config = get_restic_config(entry, credentials)

    try:
        items = list(map(json.loads, subprocess.run(
            restic_config.cmd + ["--json", "ls", snapshot_id, path],
            env=restic_config.env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()))
    except subprocess.CalledProcessError as e:
        raise CallError(e.stderr)

    contents = []
    for item in items[1:]:
        if item["struct_type"] != "node":
            continue

        item.setdefault("size", None)

        for k in ["atime", "ctime", "mtime"]:
            item[k] = datetime.fromisoformat(item[k])

        contents.append(item)

    return [CloudBackupSnapshotItem(**item) for item in contents]


def delete_snapshot(context: ServiceContext, job: Job, id_: int, snapshot_id: str) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    entry = context.call_sync2(context.s.cloud_backup.get_instance, id_)

    credentials = resolve_credentials(context, entry.credentials)
    restic_config = get_restic_config(entry, credentials)

    try:
        subprocess.run(
            restic_config.cmd + ["forget", snapshot_id, "--prune"],
            env=restic_config.env,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise CallError(e.stderr)
