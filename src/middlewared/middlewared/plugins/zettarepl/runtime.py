from __future__ import annotations

from collections import defaultdict
import queue
import threading
from typing import TYPE_CHECKING, Any

from zettarepl.observer import PeriodicSnapshotTaskError, ReplicationTaskError

from middlewared.service.part import ServicePart
from middlewared.service_exception import CallError
from middlewared.utils.string import make_sentence
from middlewared.utils.time_utils import utc_now

from .definition import build_definition as build_definition_impl
from .notify import process_notification

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

DAEMON_RESTARTED_ERROR = "The zettarepl service restarted and is no longer running this task."


class ZettareplRuntimePart(ServicePart):
    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)

        self.lock = threading.Lock()
        self.generation = 0
        self.definition: dict[str, Any] | None = None
        self.replication_jobs_channels: defaultdict[str, list[queue.Queue[Any]]] = defaultdict(list)
        self.periodic_snapshot_task_jobs_channels: defaultdict[str, list[queue.Queue[Any]]] = defaultdict(list)
        self.onetime_replication_tasks: dict[int, dict[str, Any]] = {}
        self.vm_contexts: dict[int, Any] = {}
        self.vmware_contexts: dict[int, Any] = {}

    async def is_running(self) -> bool:
        return await self.call2(self.s.service.started, "zettarepl")

    def start(self) -> None:
        self.refresh_definition()
        self.call_sync2(self.s.service.control, "START", "zettarepl")
        self.send_command({"command": "reload"}, require_running=False)

    def refresh_definition(self) -> dict[str, Any]:
        try:
            definition, hold_tasks = self.call_sync2(self.s.zettarepl.build_definition)
        except Exception as e:
            self.logger.error("Error generating zettarepl definition", exc_info=True)
            self.call_sync2(
                self.s.zettarepl.set_error,
                {
                    "state": "ERROR",
                    "datetime": utc_now(),
                    "error": make_sentence(str(e)),
                },
            )
            raise CallError(f"Internal error: {e!r}")

        self.call_sync2(self.s.zettarepl.set_error, None)

        with self.lock:
            self.generation += 1
            self.definition = definition

        self.call_sync2(self.s.zettarepl.notify_definition, definition, hold_tasks)

        return definition

    def send_command(self, command: dict[str, Any], require_running: bool = True) -> None:
        if require_running and not self.call_sync2(self.s.zettarepl.is_running):
            raise CallError("The zettarepl service is not running")

        self.middleware.send_event("zettarepl.command", "CHANGED", fields=command)

    def get_definition(self) -> dict[str, Any]:
        if self.definition is None:
            self.refresh_definition()

        with self.lock:
            return {"generation": self.generation, "definition": self.definition}

    def update_tasks(self) -> None:
        try:
            self.refresh_definition()
        except CallError:
            return

        self.send_command({"command": "reload"}, require_running=False)

    async def notify_definition_read(self, data: dict[str, Any]) -> None:
        definition_errors = {}
        for error in data["errors"]:
            if error["type"] == "periodic_snapshot_task":
                definition_errors[f"periodic_snapshot_{error['task_id']}"] = {
                    "state": "ERROR",
                    "datetime": utc_now(),
                    "error": make_sentence(error["error"]),
                }
            if error["type"] == "replication_task":
                definition_errors[f"replication_{error['task_id']}"] = {
                    "state": "ERROR",
                    "datetime": utc_now(),
                    "error": make_sentence(error["error"]),
                }

        await self.call2(self.s.zettarepl.set_definition_errors, definition_errors)

    def notify_status(self, data: dict[str, Any]) -> None:
        self.fail_unfinished_tasks(DAEMON_RESTARTED_ERROR, set(data["running"]) | set(data["pending"]))

    def notify(self, notifications: list[dict[str, Any]]) -> None:
        for notification in notifications:
            try:
                process_notification(self, notification)
            except Exception:
                self.logger.warning("Unhandled exception processing %r", notification, exc_info=True)

    def fail_unfinished_tasks(self, error: str, alive: set[str]) -> None:
        task_error_channels = [
            ("replication_", self.replication_jobs_channels, lambda task_id: ReplicationTaskError(task_id, error)),
            (
                "periodic_snapshot_",
                self.periodic_snapshot_task_jobs_channels,
                lambda task_id: PeriodicSnapshotTaskError(task_id, error),
            ),
        ]
        for k, v in self.call_sync2(self.s.zettarepl.get_state).get("tasks", {}).items():
            for prefix, channels, make_error in task_error_channels:
                if k.startswith(prefix) and v.get("state") in ("WAITING", "RUNNING"):
                    task_id = k[len(prefix) :]
                    if task_id in alive:
                        continue

                    self.call_sync2(
                        self.s.zettarepl.set_state,
                        k,
                        {
                            "state": "ERROR",
                            "datetime": utc_now(),
                            "error": error,
                        },
                    )
                    for channel in channels[task_id]:
                        channel.put(make_error(task_id))  # type: ignore[no-untyped-call]

    async def build_definition(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return await build_definition_impl(self, self.onetime_replication_tasks)

    async def periodic_snapshot_task_start(self, task_id: str) -> dict[str, Any]:
        await self.call2(
            self.s.zettarepl.set_state,
            f"periodic_snapshot_{task_id}",
            {
                "state": "RUNNING",
                "datetime": utc_now(),
            },
        )

        id_ = int(task_id.split("_")[-1])

        context = None
        if begin_context := await self.middleware.call("vmware.periodic_snapshot_task_begin", id_):
            context = await (await self.middleware.call("vmware.periodic_snapshot_task_proceed", begin_context)).wait(
                raise_error=True
            )
        self.vmware_contexts[id_] = context

        vm_context = await self.middleware.call("vm.periodic_snapshot_task_begin", id_)
        if vm_context:
            try:
                await self.middleware.call("vm.suspend_vms", list(vm_context))
            except Exception:
                self.logger.error("Failed to suspend VMs for snapshot task %r", task_id, exc_info=True)
        self.vm_contexts[id_] = vm_context

        properties = {}
        if context and context["vmsynced"]:
            # If there were no failures and we successfully took some VMWare snapshots set the ZFS property to
            # show the snapshot has consistent VM snapshots inside it.
            properties["freenas:vmsynced"] = "Y"

        return {"properties": properties}

    async def periodic_snapshot_task_end(self, task_id: str) -> None:
        id_ = int(task_id.split("_")[-1])

        context = self.vmware_contexts.pop(id_, None)
        vm_context = self.vm_contexts.pop(id_, None)

        if context:
            try:
                await (await self.middleware.call("vmware.periodic_snapshot_task_end", context)).wait(raise_error=True)
            except Exception:
                self.logger.error("Failed to finalize VMWare snapshot for task %r", task_id, exc_info=True)

        if vm_context:
            await self.middleware.call("vm.resume_suspended_vms", list(vm_context))

    async def terminate(self) -> None:
        await self.call2(self.s.zettarepl.flush_state)
        await (await self.call2(self.s.service.control, "STOP", "zettarepl")).wait()
