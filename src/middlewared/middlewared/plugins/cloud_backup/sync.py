import asyncio
import itertools

from middlewared.api import api_method
from middlewared.api.current import (
    CloudBackupSyncArgs, CloudBackupSyncResult, CloudBackupAbortArgs, CloudBackupAbortResult
)
from middlewared.plugins.cloud.path import check_local_path
from middlewared.plugins.cloud_backup.restic import get_restic_config, run_restic
from middlewared.plugins.cloud.script import env_mapping, run_script
from middlewared.plugins.cloud.snapshot import create_snapshot
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import CallError, Service, job, private
from middlewared.utils import run
from middlewared.utils.time_utils import utc_now


async def restic_backup(middleware, job, cloud_backup: dict, dry_run: bool = False, rate_limit: int | None = None):
    await middleware.call("network.general.will_perform_activity", "cloud_backup")

    snapshot = None
    clone = None
    stdin = None
    try:
        local_path = cloud_backup["path"]
        if local_path.startswith("/dev/zvol"):
            await middleware.call("cloud_backup.validate_zvol", local_path)

            name = f"cloud_backup-{cloud_backup.get('id', 'onetime')}-{utc_now().strftime('%Y%m%d%H%M%S')}"
            snapshot = (await middleware.call("pool.snapshot.create", {
                "dataset": zvol_path_to_name(local_path),
                "name": name,
                "suspend_vms": True,
                "vmware_sync": True,
            }))["name"]

            clone = zvol_path_to_name(local_path) + f"-{name}"
            try:
                await middleware.call2(
                    middleware.services.zfs.resource.snapshot.clone, {"snapshot": snapshot, "dataset": clone}
                )
            except Exception:
                clone = None
                raise

            # zvol device might take a while to appear
            for i in itertools.count():
                try:
                    stdin = await middleware.run_in_thread(open, zvol_name_to_path(clone), "rb")
                except FileNotFoundError:
                    if i >= 5:
                        raise

                    await asyncio.sleep(1)
                else:
                    break

            cwd = None
            cmd = ["--stdin", "--stdin-filename", "volume"]
        else:
            await check_local_path(middleware, local_path)
            if cloud_backup["snapshot"]:
                snapshot_name = f"cloud_backup-{cloud_backup.get('id', 'onetime')}"
                snapshot, local_path = await create_snapshot(middleware, local_path, snapshot_name)

            if cloud_backup["absolute_paths"]:
                cwd = None
                cmd = [local_path]
            else:
                cwd = local_path
                cmd = ["."]

        args = await middleware.call("cloud_backup.transfer_setting_args")
        cmd.extend(args[cloud_backup["transfer_setting"]])

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
        await run_script(job, "Pre-script", cloud_backup["pre_script"], env)

        await run_restic(job, cmd, restic_config.env, cwd=cwd, stdin=stdin, track_progress=True)

        if cloud_backup["cache_path"]:
            await run(["restic", "--cache-dir", cloud_backup["cache_path"]], "cache", "--cleanup", check=False)

        await run_script(job, "Post-script", cloud_backup["post_script"], env)
    finally:
        if stdin:
            try:
                stdin.close()
            except Exception as e:
                middleware.logger.warning(f"Error closing snapshot device: {e!r}")

        if clone is not None:
            try:
                await middleware.call2(
                    middleware.services.zfs.resource.destroy_impl,
                    clone,
                )
            except Exception as e:
                middleware.logger.warning(f"Error deleting cloned dataset {clone}: {e!r}")

        if snapshot is not None:
            try:
                await middleware.call2(
                    middleware.services.zfs.resource.snapshot.destroy_impl, {"path": snapshot}
                )
            except Exception as e:
                middleware.logger.warning(f"Error deleting snapshot {snapshot}: {e!r}")


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @api_method(CloudBackupSyncArgs, CloudBackupSyncResult, roles=['CLOUD_BACKUP_WRITE'])
    @job(lock=lambda args: "cloud_backup:{}".format(args[-1]), lock_queue_size=1, logs=True, abortable=True)
    async def sync(self, job, id_, options):
        """
        Run the cloud backup job `id`.
        """
        cloud_backup = await self.middleware.call("cloud_backup.get_instance", id_)
        if cloud_backup["locked"]:
            await self.middleware.call("cloud_backup.generate_locked_alert", id_)
            raise CallError("Dataset is locked")

        await self._sync(cloud_backup, options, job)

    async def _sync(self, cloud_backup: dict, options: dict, job):
        job.set_progress(0, "Starting")
        try:
            await self.middleware.call("cloud_backup.ensure_initialized", cloud_backup)

            await restic_backup(self.middleware, job, cloud_backup, **options)

            job.set_progress(100, "Cleaning up")
            restic_config = get_restic_config(cloud_backup)
            await run_restic(
                job,
                restic_config.cmd + ["forget", "--keep-last", str(cloud_backup["keep_last"]), "--group-by", "",
                                     "--prune"],
                restic_config.env,
            )

            if "id" in cloud_backup:
                await self.middleware.call("alert.oneshot_delete", "CloudBackupTaskFailed", cloud_backup["id"])
            job.set_progress(description="Done")
        except Exception:
            if "id" in cloud_backup:
                await self.middleware.call("alert.oneshot_create", "CloudBackupTaskFailed", {
                    "id": cloud_backup["id"],
                    "name": cloud_backup["description"],
                })
            raise

    @api_method(CloudBackupAbortArgs, CloudBackupAbortResult, roles=['CLOUD_BACKUP_WRITE'])
    async def abort(self, id_):
        """
        Abort a running cloud backup task.
        """
        cloud_backup = await self.middleware.call("cloud_backup.get_instance", id_)

        if cloud_backup["job"] is None:
            return False

        if cloud_backup["job"]["state"] not in ["WAITING", "RUNNING"]:
            return False

        await self.middleware.call("core.job_abort", cloud_backup["job"]["id"])
        return True

    @private
    async def validate_zvol(self, path):
        dataset = zvol_path_to_name(path)
        if not (
            await self.middleware.call("vm.query_snapshot_begin", dataset, False) or
            await self.middleware.call("vmware.dataset_has_vms", dataset, False)
        ):
            raise CallError("Backed up zvol must be used by a local or VMware VM")
