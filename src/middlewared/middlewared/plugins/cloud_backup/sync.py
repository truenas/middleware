from __future__ import annotations

import itertools
import subprocess
import time
from typing import IO, TYPE_CHECKING, Any, Literal

from middlewared.api.current import (
    CloudBackupSyncOptions,
    ZFSResourceSnapshotCloneQuery,
    ZFSResourceSnapshotDestroyQuery,
)
from middlewared.plugins.cloud.path import check_local_path
from middlewared.plugins.cloud.script import env_mapping, run_script
from middlewared.plugins.cloud.snapshot import create_snapshot
from middlewared.plugins.cloud_backup.crud import CloudBackupTaskFailedAlert
from middlewared.plugins.cloud_backup.init import ensure_initialized
from middlewared.plugins.cloud_backup.restic import get_restic_config, run_restic
from middlewared.plugins.cloud_backup.utils import revealed_dict
from middlewared.plugins.zfs.zvol_utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import CallError, ServiceContext
from middlewared.utils.time_utils import utc_now

if TYPE_CHECKING:
    from middlewared.job import Job


TRANSFER_SETTING_ARGS: dict[Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"], list[str]] = {
    "DEFAULT": [],
    "PERFORMANCE": ["--pack-size", "29"],
    "FAST_STORAGE": ["--pack-size", "58", "--read-concurrency", "100"],
}


def restic_backup(
    context: ServiceContext,
    job: Job,
    cloud_backup: dict[str, Any],
    dry_run: bool = False,
    rate_limit: int | None = None,
) -> None:
    middleware = context.middleware
    middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    snapshot = None
    clone = None
    stdin: IO[bytes] | None = None
    try:
        local_path = cloud_backup["path"]
        if local_path.startswith("/dev/zvol"):
            context.call_sync2(context.s.cloud_backup.validate_zvol, local_path)

            name = f"cloud_backup-{cloud_backup.get('id', 'onetime')}-{utc_now().strftime('%Y%m%d%H%M%S')}"
            snapshot = (middleware.call_sync("pool.snapshot.create", {
                "dataset": zvol_path_to_name(local_path),
                "name": name,
                "suspend_vms": True,
                "vmware_sync": True,
            }))["name"]

            clone = zvol_path_to_name(local_path) + f"-{name}"
            try:
                context.call_sync2(
                    context.s.zfs.resource.snapshot.clone,
                    ZFSResourceSnapshotCloneQuery(snapshot=snapshot, dataset=clone),
                )
            except Exception:
                clone = None
                raise

            # zvol device might take a while to appear
            for i in itertools.count():
                try:
                    stdin = open(zvol_name_to_path(clone), "rb")
                except FileNotFoundError:
                    if i >= 5:
                        raise

                    time.sleep(1)
                else:
                    break

            cwd = None
            cmd = ["--stdin", "--stdin-filename", "volume"]
        else:
            check_local_path(middleware, local_path)
            if cloud_backup["snapshot"]:
                snapshot_name = f"cloud_backup-{cloud_backup.get('id', 'onetime')}"
                snapshot, local_path = create_snapshot(middleware, local_path, snapshot_name)

            if cloud_backup["absolute_paths"]:
                cwd = None
                cmd = [local_path]
            else:
                cwd = local_path
                cmd = ["."]

        cmd.extend(TRANSFER_SETTING_ARGS[cloud_backup["transfer_setting"]])

        if dry_run:
            cmd.append("-n")
        if limit := (rate_limit or cloud_backup["rate_limit"]):
            cmd.append(f"--limit-upload={limit}")

        cmd.extend(["--exclude=" + excl for excl in cloud_backup["exclude"]])

        restic_config = get_restic_config(cloud_backup)
        cmd = restic_config.cmd + ["--verbose", "backup"] + cmd

        env = env_mapping("CLOUD_BACKUP_", {
            **{k: v for k, v in cloud_backup.items() if k in [
                "id", "description", "snapshot", "password", "keep_last", "transfer_setting"
            ]},
            **cloud_backup["credentials"]["provider"],
            **cloud_backup["attributes"],
            "path": local_path
        })
        run_script(job, "Pre-script", cloud_backup["pre_script"], env)

        run_restic(job, cmd, restic_config.env, cwd=cwd, stdin=stdin, track_progress=True)

        if cloud_backup["cache_path"]:
            subprocess.run(["restic", "--cache-dir", cloud_backup["cache_path"], "cache", "--cleanup"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        run_script(job, "Post-script", cloud_backup["post_script"], env)
    finally:
        if stdin:
            try:
                stdin.close()
            except Exception as e:
                context.logger.warning(f"Error closing snapshot device: {e!r}")

        if clone is not None:
            try:
                context.call_sync2(context.s.zfs.resource.destroy_impl, clone)
            except Exception as e:
                context.logger.warning(f"Error deleting cloned dataset {clone}: {e!r}")

        if snapshot is not None:
            try:
                context.call_sync2(
                    context.s.zfs.resource.snapshot.destroy_impl,
                    ZFSResourceSnapshotDestroyQuery(path=snapshot),
                )
            except Exception as e:
                context.logger.warning(f"Error deleting snapshot {snapshot}: {e!r}")


def do_sync(context: ServiceContext, job: Job, id_: int, options: CloudBackupSyncOptions) -> None:
    entry = context.call_sync2(context.s.cloud_backup.get_instance, id_)
    if entry.locked:
        context.call_sync2(context.s.cloud_backup.generate_locked_alert, id_)
        raise CallError("Dataset is locked")

    _sync(context, revealed_dict(context, entry), options, job)


def _sync(context: ServiceContext, cloud_backup: dict[str, Any], options: CloudBackupSyncOptions, job: Job) -> None:
    job.set_progress(0, "Starting")
    try:
        ensure_initialized(context, cloud_backup)

        restic_backup(context, job, cloud_backup, dry_run=options.dry_run, rate_limit=options.rate_limit)

        job.set_progress(100, "Cleaning up")
        restic_config = get_restic_config(cloud_backup)
        run_restic(
            job,
            restic_config.cmd + ["forget", "--keep-last", str(cloud_backup["keep_last"]), "--group-by", "", "--prune"],
            restic_config.env,
        )

        if "id" in cloud_backup:
            context.call_sync2(context.s.alert.oneshot_delete, "CloudBackupTaskFailed", cloud_backup["id"])
        job.set_progress(description="Done")
    except Exception:
        if "id" in cloud_backup:
            context.call_sync2(context.s.alert.oneshot_create, CloudBackupTaskFailedAlert(
                id=cloud_backup["id"],
                name=cloud_backup["description"],
            ))
        raise


def do_abort(context: ServiceContext, id_: int) -> bool:
    entry = context.call_sync2(context.s.cloud_backup.get_instance, id_)

    if entry.job is None:
        return False

    if entry.job["state"] not in ["WAITING", "RUNNING"]:
        return False

    context.middleware.call_sync("core.job_abort", entry.job["id"])
    return True
