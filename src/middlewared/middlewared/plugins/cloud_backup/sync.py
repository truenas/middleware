import asyncio
import itertools

from middlewared.plugins.cloud.path import check_local_path
from middlewared.plugins.cloud_backup.restic import get_restic_config, run_restic
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.schema import accepts, Bool, Dict, Int
from middlewared.service import CallError, Service, item_method, job, private
from middlewared.utils.time_utils import utc_now


async def restic(middleware, job, cloud_backup, dry_run):
    await middleware.call("network.general.will_perform_activity", "cloud_backup")

    snapshot = None
    clone = None
    stdin = None
    cmd = None
    try:
        local_path = cloud_backup["path"]
        if local_path.startswith("/dev/zvol"):
            await middleware.call("cloud_backup.validate_zvol", local_path)

            name = f"cloud_backup-{cloud_backup.get('id', 'onetime')}-{utc_now().strftime('%Y%m%d%H%M%S')}"
            snapshot = (await middleware.call("zfs.snapshot.create", {
                "dataset": zvol_path_to_name(local_path),
                "name": name,
                "suspend_vms": True,
                "vmware_sync": True,
            }))["name"]

            clone = zvol_path_to_name(local_path) + f"-{name}"
            try:
                await middleware.call("zfs.snapshot.clone", {
                    "snapshot": snapshot,
                    "dataset_dst": clone,
                })
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

            cmd = ["--stdin", "--stdin-filename", "volume"]
        else:
            await check_local_path(middleware, local_path)

        if cmd is None:
            cmd = [local_path]

        if dry_run:
            cmd.append("-n")

        restic_config = get_restic_config(cloud_backup)

        cmd = restic_config.cmd + ["--verbose", "backup"] + cmd

        await run_restic(job, cmd, restic_config.env, stdin, track_progress=True)
    finally:
        if stdin:
            try:
                stdin.close()
            except Exception as e:
                middleware.logger.warning(f"Error closing snapshot device: {e!r}")

        if clone is not None:
            try:
                await middleware.call("zfs.dataset.delete", clone)
            except Exception as e:
                middleware.logger.warning(f"Error deleting cloned dataset {clone}: {e!r}")

        if snapshot is not None:
            try:
                await middleware.call("zfs.snapshot.delete", snapshot)
            except Exception as e:
                middleware.logger.warning(f"Error deleting snapshot {snapshot}: {e!r}")


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @item_method
    @accepts(
        Int("id"),
        Dict(
            "cloud_backup_sync_options",
            Bool("dry_run", default=False),
            register=True,
        )
    )
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

    async def _sync(self, cloud_backup, options, job):
        job.set_progress(0, "Starting")
        try:
            await self.middleware.call("cloud_backup.ensure_initialized", cloud_backup)

            await restic(self.middleware, job, cloud_backup, options["dry_run"])

            job.set_progress(100, "Cleaning up")
            restic_config = get_restic_config(cloud_backup)
            await run_restic(
                job,
                restic_config.cmd + ["forget", "--keep-last", str(cloud_backup["keep_last"])],
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

    @item_method
    @accepts(Int("id"))
    async def abort(self, id_):
        """
        Aborts cloud backup task.
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
