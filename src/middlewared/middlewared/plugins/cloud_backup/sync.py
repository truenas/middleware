import asyncio
import subprocess

from middlewared.plugins.cloud.path import get_remote_path, check_local_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.schema import accepts, Bool, Dict, Int
from middlewared.service import CallError, Service, item_method, job
from middlewared.utils import Popen


async def restic(middleware, job, cloud_backup, dry_run):
    await middleware.call("network.general.will_perform_activity", "cloud_backup")

    remote = REMOTES[cloud_backup["credentials"]["provider"]]

    if await middleware.call("filesystem.is_cluster_path", cloud_backup["path"]):
        local_path = await middleware.call("filesystem.resolve_cluster_path", cloud_backup["path"])
        await check_local_path(
            middleware,
            local_path,
            check_mountpoint=False,
            error_text_path=cloud_backup["path"],
        )
    else:
        local_path = cloud_backup["path"]
        await check_local_path(middleware, local_path)

    remote_path = get_remote_path(remote, cloud_backup["attributes"])

    url, env = remote.get_restic_config(cloud_backup)

    cmd = ["restic", "-r", f"{remote.rclone_type}:{url}/{remote_path}", "--verbose", "backup", local_path]
    if dry_run:
        cmd.append("-n")

    env["RESTIC_PASSWORD"] = cloud_backup["password"]

    job.middleware.logger.debug("Running %r", cmd)
    proc = await Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    check_progress = asyncio.ensure_future(restic_check_progress(job, proc))
    cancelled_error = None
    try:
        try:
            await proc.wait()
        except asyncio.CancelledError as e:
            cancelled_error = e
            try:
                await middleware.call("service.terminate_process", proc.pid)
            except CallError as e:
                job.middleware.logger.warning(f"Error terminating restic on cloud backup abort: {e!r}")
    finally:
        await asyncio.wait_for(check_progress, None)

    if cancelled_error is not None:
        raise cancelled_error
    if proc.returncode != 0:
        message = "".join(job.internal_data.get("messages", []))
        if message and proc.returncode != 1:
            if message and not message.endswith("\n"):
                message += "\n"
            message += f"restic failed with exit code {proc.returncode}"
        raise CallError(message)


async def restic_check_progress(job, proc):
    try:
        while True:
            read = (await proc.stdout.readline()).decode("utf-8", "ignore")
            if read == "":
                break

            await job.logs_fd_write(read.encode("utf-8", "ignore"))

            job.internal_data.setdefault("messages", [])
            job.internal_data["messages"] = job.internal_data["messages"][-4:] + [read]
    finally:
        pass


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @item_method
    @accepts(Int("id"))
    @job()
    def init(self, job_id, id):
        """
        Initializes the repository for the cloud backup job `id`.
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        cloud_backup = self.middleware.call_sync("cloud_backup.get_instance", id)

        remote = REMOTES[cloud_backup["credentials"]["provider"]]

        remote_path = get_remote_path(remote, cloud_backup["attributes"])

        url, env = remote.get_restic_config(cloud_backup)

        try:
            subprocess.run([
                "restic", "init", "-r", f"{remote.rclone_type}:{url}/{remote_path}",
            ], env={
                "RESTIC_PASSWORD": cloud_backup["password"],
                **env,
            }, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise CallError(e.stderr)

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
    async def sync(self, job, id, options):
        """
        Run the cloud backup job `id`.
        """

        cloud_backup = await self.middleware.call("cloud_backup.get_instance", id)
        if cloud_backup["locked"]:
            await self.middleware.call("cloud_backup.generate_locked_alert", id)
            raise CallError("Dataset is locked")

        await self._sync(cloud_backup, options, job)

    async def _sync(self, cloud_backup, options, job):
        job.set_progress(0, "Starting")
        try:
            await restic(self.middleware, job, cloud_backup, options["dry_run"])

            if "id" in cloud_backup:
                await self.middleware.call("alert.oneshot_delete", "CloudBackupTaskFailed", cloud_backup["id"])
        except Exception:
            if "id" in cloud_backup:
                await self.middleware.call("alert.oneshot_create", "CloudBackupTaskFailed", {
                    "id": cloud_backup["id"],
                    "name": cloud_backup["description"],
                })
            raise

    @item_method
    @accepts(Int("id"))
    async def abort(self, id):
        """
        Aborts cloud backup task.
        """
        cloud_backup = await self.middleware.call("cloud_backup.get_instance", id)

        if cloud_backup["job"] is None:
            return False

        if cloud_backup["job"]["state"] not in ["WAITING", "RUNNING"]:
            return False

        await self.middleware.call("core.job_abort", cloud_backup["job"]["id"])
        return True
