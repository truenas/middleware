from datetime import datetime
import json
import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    CloudBackupListSnapshotsArgs, CloudBackupListSnapshotsResult, CloudBackupListSnapshotDirectoryArgs,
    CloudBackupListSnapshotDirectoryResult, CloudBackupDeleteSnapshotArgs, CloudBackupDeleteSnapshotResult
)
from middlewared.plugins.cloud_backup.restic import get_restic_config
from middlewared.service import CallError, job, Service


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @api_method(CloudBackupListSnapshotsArgs, CloudBackupListSnapshotsResult)
    def list_snapshots(self, id_):
        """
        List existing snapshots for the cloud backup job `id`.
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        cloud_backup = self.middleware.call_sync("cloud_backup.get_instance", id_)

        restic_config = get_restic_config(cloud_backup)

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

        return snapshots

    @api_method(CloudBackupListSnapshotDirectoryArgs, CloudBackupListSnapshotDirectoryResult)
    def list_snapshot_directory(self, id_, snapshot_id, path):
        """
        List files in the directory `path` of the `snapshot_id` created by the cloud backup job `id`.
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        cloud_backup = self.middleware.call_sync("cloud_backup.get_instance", id_)

        restic_config = get_restic_config(cloud_backup)

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

        return contents

    @api_method(CloudBackupDeleteSnapshotArgs, CloudBackupDeleteSnapshotResult)
    @job(lock=lambda args: "cloud_backup:{}".format(args[-1]), lock_queue_size=1)
    def delete_snapshot(self, job, id_, snapshot_id):
        """
        Delete snapshot `snapshot_id` created by the cloud backup job `id`.
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        cloud_backup = self.middleware.call_sync("cloud_backup.get_instance", id_)

        restic_config = get_restic_config(cloud_backup)

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
