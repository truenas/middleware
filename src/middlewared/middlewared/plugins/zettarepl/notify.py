from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zettarepl.observer import (
    ObserverMessage,
    PeriodicSnapshotTaskError,
    PeriodicSnapshotTaskSuccess,
    ReplicationTaskDataProgress,
    ReplicationTaskError,
    ReplicationTaskLog,
    ReplicationTaskScheduled,
    ReplicationTaskSnapshotProgress,
    ReplicationTaskSnapshotStart,
    ReplicationTaskSnapshotSuccess,
    ReplicationTaskStart,
    ReplicationTaskSuccess,
)

from middlewared.api.current import ReplicationRunOptions
from middlewared.utils.string import make_sentence
from middlewared.utils.time_utils import utc_now

if TYPE_CHECKING:
    from .runtime import ZettareplRuntimePart


def process_notification(part: ZettareplRuntimePart, notification: dict[str, Any]) -> None:
    message = ObserverMessage.load(notification)

    part.logger.trace("zettarepl notified %r", message)  # type: ignore[attr-defined]

    if isinstance(message, PeriodicSnapshotTaskSuccess):
        part.s.zettarepl.state.set_last_snapshot(
            f"periodic_snapshot_{message.task_id}",
            f"{message.dataset}@{message.snapshot}",
        )

        part.s.zettarepl.state.set_state(
            f"periodic_snapshot_{message.task_id}",
            {
                "state": "FINISHED",
                "datetime": utc_now(),
            },
        )

        for channel in part.periodic_snapshot_task_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, PeriodicSnapshotTaskError):
        part.s.zettarepl.state.set_state(
            f"periodic_snapshot_{message.task_id}",
            {
                "state": "ERROR",
                "datetime": utc_now(),
                "error": make_sentence(message.error),
            },
        )

        for channel in part.periodic_snapshot_task_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskScheduled):
        state = part.s.zettarepl.state.get_state_internal(f"replication_{message.task_id}")
        if (state or {}).get("state") != "RUNNING":
            part.s.zettarepl.state.set_state(
                f"replication_{message.task_id}",
                {
                    "state": "WAITING",
                    "datetime": utc_now(),
                    "reason": message.waiting_reason,
                },
            )

    if isinstance(message, ReplicationTaskStart):
        part.s.zettarepl.state.set_state(
            f"replication_{message.task_id}",
            {
                "state": "RUNNING",
                "datetime": utc_now(),
            },
        )

        # Start fake job if none are already running
        if not part.replication_jobs_channels[message.task_id]:
            part.call_sync2(part.s.replication.run, int(message.task_id[5:]), ReplicationRunOptions(really_run=False))

    if isinstance(message, ReplicationTaskLog):
        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskSnapshotStart):
        part.s.zettarepl.state.set_state(
            f"replication_{message.task_id}",
            {
                "state": "RUNNING",
                "datetime": utc_now(),
                "progress": {
                    "dataset": message.dataset,
                    "snapshot": message.snapshot,
                    "snapshots_sent": message.snapshots_sent,
                    "snapshots_total": message.snapshots_total,
                    "bytes_sent": 0,
                    "bytes_total": 0,
                    # legacy
                    "current": 0,
                    "total": 0,
                },
            },
        )

        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskSnapshotProgress):
        part.s.zettarepl.state.set_state(
            f"replication_{message.task_id}",
            {
                "state": "RUNNING",
                "datetime": utc_now(),
                "progress": {
                    "dataset": message.dataset,
                    "snapshot": message.snapshot,
                    "snapshots_sent": message.snapshots_sent,
                    "snapshots_total": message.snapshots_total,
                    "bytes_sent": message.bytes_sent,
                    "bytes_total": message.bytes_total,
                    # legacy
                    "current": message.bytes_sent,
                    "total": message.bytes_total,
                },
            },
        )

        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskSnapshotSuccess):
        part.s.zettarepl.state.set_last_snapshot(
            f"replication_{message.task_id}",
            f"{message.dataset}@{message.snapshot}",
        )

        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskDataProgress):
        task_id = f"replication_{message.task_id}"
        try:
            state = part.s.zettarepl.state.get_internal_task_state(task_id)
        except KeyError:
            pass
        else:
            if state["state"] == "RUNNING" and "progress" in state:
                state["progress"].update(
                    {
                        "root_dataset": message.dataset,
                        "src_size": message.src_size,
                        "dst_size": message.dst_size,
                    }
                )
                part.s.zettarepl.state.set_state(task_id, state)

        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskSuccess):
        part.s.zettarepl.state.set_state(
            f"replication_{message.task_id}",
            {
                "state": "FINISHED",
                "datetime": utc_now(),
                "warnings": message.warnings,
            },
        )

        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)

    if isinstance(message, ReplicationTaskError):
        part.s.zettarepl.state.set_state(
            f"replication_{message.task_id}",
            {
                "state": "ERROR",
                "datetime": utc_now(),
                "error": make_sentence(message.error),
            },
        )

        for channel in part.replication_jobs_channels[message.task_id]:
            channel.put(message)
