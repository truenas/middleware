from __future__ import annotations

import errno
import queue
from typing import TYPE_CHECKING, Any

from zettarepl.observer import (
    PeriodicSnapshotTaskError,
    PeriodicSnapshotTaskSuccess,
    ReplicationTaskDataProgress,
    ReplicationTaskError,
    ReplicationTaskLog,
    ReplicationTaskSnapshotProgress,
    ReplicationTaskSnapshotStart,
    ReplicationTaskSuccess,
)

from middlewared.service_exception import CallError
from middlewared.utils.size import format_size
from middlewared.utils.string import make_sentence

if TYPE_CHECKING:
    from middlewared.job import Job

    from .runtime import ZettareplRuntimePart


def run_periodic_snapshot_task(part: ZettareplRuntimePart, id_: int) -> None:
    part.send_command(
        {
            "command": "run_task",
            "class_name": "PeriodicSnapshotTask",
            "task_id": f"task_{id_}",
        }
    )

    channels = part.periodic_snapshot_task_jobs_channels[f"task_{id_}"]
    channel: queue.Queue[Any] = queue.Queue()
    channels.append(channel)
    try:
        while True:
            message = channel.get()

            if isinstance(message, PeriodicSnapshotTaskSuccess):
                if message.already_existed:
                    raise CallError(
                        f"Snapshot {message.dataset}@{message.snapshot} already existed. "
                        "This probably happened because the task already ran on schedule.",
                        errno.EEXIST,
                    )
                return

            if isinstance(message, PeriodicSnapshotTaskError):
                raise CallError(make_sentence(message.error))
    finally:
        channels.remove(channel)


def run_replication_task(part: ZettareplRuntimePart, id_: int, really_run: bool, job: Job) -> None:
    if really_run:
        part.send_command(
            {
                "command": "run_task",
                "class_name": "ReplicationTask",
                "task_id": f"task_{id_}",
            }
        )

    run_replication_task_job(part, f"task_{id_}", job)


def run_onetime_replication_task(part: ZettareplRuntimePart, job: Job, task: dict[str, Any]) -> None:
    job_id = job.id
    assert job_id is not None
    part.onetime_replication_tasks[job_id] = task
    try:
        part.update_tasks()

        state = part.call_sync2(part.s.zettarepl.get_state)
        if "error" in state:
            raise CallError(state["error"])
        task_state = state["tasks"].get(f"job_{job_id}")
        if task_state:
            if task_state["state"] == "ERROR":
                raise CallError(task_state["error"])
            if task_state["state"] == "HOLD":
                raise CallError(task_state["reason"])
            if task_state["state"] != "WAITING":
                raise CallError(task_state)

        part.send_command(
            {
                "command": "run_task",
                "class_name": "ReplicationTask",
                "task_id": f"job_{job_id}",
            }
        )

        run_replication_task_job(part, f"job_{job_id}", job)
    finally:
        part.onetime_replication_tasks.pop(job_id)
        part.update_tasks()


def run_replication_task_job(part: ZettareplRuntimePart, id_: str, job: Job) -> None:
    channels = part.replication_jobs_channels[id_]
    channel: queue.Queue[Any] = queue.Queue()
    channels.append(channel)
    snapshot_start_message = None
    snapshot_progress_message = None
    data_progress_message = None
    try:
        while True:
            message = channel.get()

            if isinstance(message, ReplicationTaskLog):
                assert job.logs_fd is not None
                job.logs_fd.write(message.log.encode("utf8", "ignore") + b"\n")

            if isinstance(message, ReplicationTaskSnapshotStart):
                snapshot_start_message = message
                snapshot_progress_message = None
                set_replication_task_progress(
                    job, snapshot_start_message, snapshot_progress_message, data_progress_message
                )

            if isinstance(message, ReplicationTaskSnapshotProgress):
                snapshot_progress_message = message
                set_replication_task_progress(
                    job, snapshot_start_message, snapshot_progress_message, data_progress_message
                )

            if isinstance(message, ReplicationTaskDataProgress):
                data_progress_message = message
                set_replication_task_progress(
                    job, snapshot_start_message, snapshot_progress_message, data_progress_message
                )

            if isinstance(message, ReplicationTaskSuccess):
                return

            if isinstance(message, ReplicationTaskError):
                raise CallError(make_sentence(message.error))
    finally:
        channels.remove(channel)


def set_replication_task_progress(
    job: Job,
    snapshot_start_message: ReplicationTaskSnapshotStart | None,
    snapshot_progress_message: ReplicationTaskSnapshotProgress | None,
    data_progress_message: ReplicationTaskDataProgress | None,
) -> None:
    if snapshot_start_message is None:
        return

    if snapshot_progress_message is None:
        progress = 100 * (snapshot_start_message.snapshots_sent / snapshot_start_message.snapshots_total)
        text = (
            f"Sending {snapshot_start_message.snapshots_sent + 1} of {snapshot_start_message.snapshots_total}: "
            f"{snapshot_start_message.dataset}@{snapshot_start_message.snapshot}"
        )
    else:
        progress = 100 * (
            (
                snapshot_progress_message.snapshots_sent
                + snapshot_progress_message.bytes_sent / (snapshot_progress_message.bytes_total or float("inf"))
            )
            / snapshot_progress_message.snapshots_total
        )
        text = (
            f"Sending {snapshot_progress_message.snapshots_sent + 1} of "
            f"{snapshot_progress_message.snapshots_total}: "
            f"{snapshot_progress_message.dataset}@{snapshot_progress_message.snapshot} "
            f"({format_size(snapshot_progress_message.bytes_sent)} / "
            f"{format_size(snapshot_progress_message.bytes_total)})"
        )

    if data_progress_message is not None:
        # Destination can result being larger than source.
        # Do this to avoid displaying progress like "[total 11.11 TiB out of 11.04 TiB]".
        total = max(data_progress_message.dst_size, data_progress_message.src_size)
        text += f" [total {format_size(data_progress_message.dst_size)} of {format_size(total)}]"

    job.set_progress(progress, text)
