import asyncio
from dataclasses import dataclass
from datetime import timedelta
import json
import subprocess

from middlewared.job import JobProgressBuffer
from middlewared.plugins.cloud.path import get_remote_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.service import CallError
from middlewared.utils import Popen


@dataclass
class ResticConfig:
    cmd: list[str]
    env: dict[str, str]


def get_restic_config(cloud_backup):
    remote = REMOTES[cloud_backup["credentials"]["provider"]]

    remote_path = get_remote_path(remote, cloud_backup["attributes"])

    url, env = remote.get_restic_config(cloud_backup)

    cmd = ["restic", "--no-cache", "--json", "-r", f"{remote.rclone_type}:{url}/{remote_path}"]

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
    check_progress = asyncio.ensure_future(restic_check_progress(job, proc, cmd))
    cancelled_error = None
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
        message = "\n".join(job.internal_data.get("messages", []))
        if message and proc.returncode != 1:
            if not message.endswith("\n"):
                message += "\n"
            message += f"restic failed with exit code {proc.returncode}"
        raise CallError(message)


async def restic_check_progress(job, proc, cmd: list[str]):
    """Record progress of restic backup, restore, and forget commands.

    Relevant documentation: https://restic.readthedocs.io/en/stable/075_scripting.html#json-output

    """
    if "forget" in cmd:
        read = await proc.stdout.read()
        await job.logs_fd_write(read)
        return

    # backup or restore
    job.internal_data.setdefault("messages", [])
    progress_buffer = JobProgressBuffer(job)
    time_delta = ""
    action = ""
    while True:
        read = (await proc.stdout.readline()).decode("utf-8", "ignore")
        if read == "":
            break

        read = json.loads(read)
        msg_type = read["message_type"]
        if msg_type == "status":
            if (remaining := read.get("seconds_remaining")) is not None:
                time_delta = str(timedelta(seconds=remaining))

            progress_buffer.set_progress(
                read["percent_done"] * 100,
                (f"{time_delta} remaining.  " if time_delta else "") + action
            )
            continue

        await job.logs_fd_write((json.dumps(read) + "\n").encode("utf-8", "ignore"))
        if msg_type == "summary":
            continue

        if msg_type == "error":
            action = read["error.message"]
            msg = "".join([
                "Error",
                f" in {item}" if (item := read.get("item")) else "",
                f" while {during}" if (during := read.get("during")) else "",
                ": ",
                action
            ])
        else:
            # verbose_status
            action = " ".join([read[key] for key in ("item", "action") if key in read])
            msg = action

        job.internal_data["messages"] = job.internal_data["messages"][-4:] + [msg]
        progress_buffer.set_progress(description=(f"{time_delta} remaining.  " if time_delta else "") + action)
