import asyncio
from dataclasses import dataclass
import subprocess

from middlewared.plugins.cloud.path import get_remote_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.service import CallError
from middlewared.utils import Popen


@dataclass
class ResticConfig:
    cmd: [str]
    env: {str: str}


def get_restic_config(cloud_backup):
    remote = REMOTES[cloud_backup["credentials"]["provider"]]

    remote_path = get_remote_path(remote, cloud_backup["attributes"])

    url, env = remote.get_restic_config(cloud_backup)

    cmd = ["restic", "--no-cache", "-r", f"{remote.rclone_type}:{url}/{remote_path}"]

    env["RESTIC_PASSWORD"] = cloud_backup["password"]

    return ResticConfig(cmd, env)


async def run_restic(job, cmd, env, stdin=None):
    job.middleware.logger.debug("Running %r", cmd)
    proc = await Popen(
        cmd,
        env=env,
        stdin=stdin,
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
                await job.middleware.call("service.terminate_process", proc.pid)
            except CallError as e:
                job.middleware.logger.warning(f"Error terminating restic on cloud backup abort: {e!r}")
    finally:
        await asyncio.wait_for(check_progress, None)

    if cancelled_error is not None:
        raise cancelled_error
    if proc.returncode != 0:
        message = "".join(job.internal_data.get("messages", []))
        if message and proc.returncode != 1:
            if not message.endswith("\n"):
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
