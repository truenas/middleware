from dataclasses import dataclass
from datetime import timedelta
import json
import subprocess
import threading

from middlewared.job import JobCancelledException, JobProgressBuffer
from middlewared.plugins.cloud.path import get_remote_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.service import CallError


@dataclass
class ResticConfig:
    cmd: list[str]
    env: dict[str, str]


def get_restic_config(cloud_backup):
    remote = REMOTES[cloud_backup["credentials"]["provider"]["type"]]

    remote_path = get_remote_path(remote, cloud_backup["attributes"])

    url, env = remote.get_restic_config(cloud_backup)

    if cloud_backup["cache_path"]:
        cache = ["--cache-dir", cloud_backup["cache_path"]]
    else:
        cache = ["--no-cache"]

    cmd = ["restic"] + cache + ["--json", "-r", f"{remote.rclone_type}:{url}/{remote_path}"]

    env["RESTIC_PASSWORD"] = cloud_backup["password"]

    return ResticConfig(cmd, env)


def run_restic(job, cmd, env, *, cwd=None, stdin=None, track_progress=False):
    job.logs_fd.write((json.dumps(cmd) + "\n").encode("utf-8", "ignore"))
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Run progress check in a thread
    check_progress_thread = threading.Thread(
        target=restic_check_progress,
        args=(job, proc, track_progress)
    )
    check_progress_thread.start()

    aborted = False
    try:
        while proc.poll() is None:
            if job.aborted_event.wait(timeout=0.2):
                aborted = True
                try:
                    job.middleware.call_sync("service.terminate_process", proc.pid)
                except CallError as e:
                    job.middleware.logger.warning(f"Error terminating restic on cloud backup abort: {e!r}")
                    break
    finally:
        check_progress_thread.join()

    if aborted:
        raise JobCancelledException()
    if proc.returncode != 0:
        message = "\n".join(job.internal_data.get("messages", []))
        if message and proc.returncode != 1:
            if not message.endswith("\n"):
                message += "\n"
            message += f"restic failed with exit code {proc.returncode}"
        raise CallError(message)


def restic_check_progress(job, proc, track_progress=False):
    """Record progress of restic backup, restore, and forget commands.

    `track_progress` cannot be set when running "restic forget".

    Relevant documentation: https://restic.readthedocs.io/en/stable/075_scripting.html#json-output

    """
    if not track_progress:
        read = proc.stdout.read()
        job.logs_fd.write(read)
        return

    # backup or restore
    job.internal_data.setdefault("messages", [])
    progress_buffer = JobProgressBuffer(job)
    time_delta = ""
    action = ""
    while True:
        read = proc.stdout.readline().decode("utf-8", "ignore")
        if read == "":
            break

        try:
            read = json.loads(read)
        except json.JSONDecodeError:
            # Can happen with some error messages
            job.internal_data["messages"] = job.internal_data["messages"][-4:] + [read]
            job.logs_fd.write((read + "\n").encode("utf-8", "ignore"))
            continue

        msg = None
        msg_type = read["message_type"]
        match msg_type:
            case "status":
                if (remaining := read.get("seconds_remaining")) is not None:
                    try:
                        time_delta = str(timedelta(seconds=remaining))
                    except OverflowError:
                        # Invalid `restic` output yields to
                        # OverflowError: Python int too large to convert to C int
                        # OverflowError: days=1785711940; must have magnitude <= 999999999
                        pass

                progress_buffer.set_progress(
                    read["percent_done"] * 100,
                    (f"{time_delta} remaining\n" if time_delta else "") + action
                )
                continue

            case "verbose_status":
                action = " ".join([read[key] for key in ("item", "action") if key in read])
                msg = action

            case "summary":
                job.logs_fd.write((json.dumps(read) + "\n").encode("utf-8", "ignore"))
                job.logs_excerpt = "\n".join(f"{k}: {v}" for k, v in read.items())
                continue

            case "error":
                action = read["error.message"]
                msg = "".join([
                    "Error",
                    f" in {item}" if (item := read.get("item")) else "",
                    f" while {during}" if (during := read.get("during")) else "",
                    ": ",
                    action
                ])
                job.logs_fd.write((json.dumps(read) + "\n").encode("utf-8", "ignore"))

        if msg:
            job.internal_data["messages"] = job.internal_data["messages"][-4:] + [msg]

        progress_buffer.set_progress(description=(f"{time_delta} remaining\n" if time_delta else "") + action)
