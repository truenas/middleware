from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import time as _time
from datetime import timedelta
import errno
import queue
import re
import socket
import threading
import types

import paramiko.ssh_exception
from zettarepl.dataset.create import create_dataset
from zettarepl.dataset.list import list_datasets
from zettarepl.definition.definition import Definition
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
from zettarepl.replication.task.dataset import get_target_dataset
from zettarepl.replication.task.name_pattern import compile_name_regex
from zettarepl.snapshot.list import group_snapshots_by_datasets, multilist_snapshots
from zettarepl.snapshot.name import parse_snapshots_names_with_multiple_schemas
from zettarepl.transport.create import create_transport
from zettarepl.transport.local import LocalShell

from middlewared.api.current import PeriodicSnapshotTaskEntry, ReplicationRunOptions
from middlewared.plugins.zettarepl_.state import PERIODIC_SNAPSHOT_TASK_STATE, REPLICATION_TASK_STATE
from middlewared.service.service import Service
from middlewared.service_exception import CallError
from middlewared.utils.size import format_size
from middlewared.utils.string import make_sentence
from middlewared.utils.time_utils import utc_now
from middlewared.utils.timezone_choices import effective_timezone

INVALID_DATASETS = (
    re.compile(r"boot-pool($|/)"),
    re.compile(r"freenas-boot($|/)"),
    re.compile(r"[^/]+/\.system($|/)")
)

DAEMON_RESTARTED_ERROR = "The zettarepl service restarted and is no longer running this task."


def lifetime_timedelta(value, unit):
    if unit == "HOUR":
        return timedelta(hours=value)

    if unit == "DAY":
        return timedelta(days=value)

    if unit == "WEEK":
        return timedelta(weeks=value)

    if unit == "MONTH":
        return timedelta(days=value * 30)

    if unit == "YEAR":
        return timedelta(days=value * 365)

    raise ValueError(f"Invalid lifetime unit: {unit!r}")


def timedelta_iso8601(timedelta):
    return f"PT{int(timedelta.total_seconds())}S"


def lifetime_iso8601(value, unit):
    return timedelta_iso8601(lifetime_timedelta(value, unit))


def replication_task_exclude(replication_task):
    exclude = list(replication_task["exclude"])
    if replication_task["recursive"] and not replication_task["replicate"]:
        for ds in replication_task["source_datasets"]:
            # Exclude all possible FreeNAS system datasets
            if "/" not in ds:
                exclude.append(f"{ds}/.system")

    return exclude


def zettarepl_schedule(schedule):
    schedule = {k.replace("_", "-"): v for k, v in schedule.items()}
    schedule["day-of-month"] = schedule.pop("dom")
    schedule["day-of-week"] = schedule.pop("dow")
    for k in ["begin", "end"]:
        if k in schedule and isinstance(schedule[k], _time):
            schedule[k] = str(schedule[k])[:5]

    return schedule


class HoldReplicationTaskException(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__()


class ZettareplService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lock = threading.Lock()
        self.generation = 0
        self.definition = None
        self.replication_jobs_channels = defaultdict(list)
        self.periodic_snapshot_task_jobs_channels = defaultdict(list)
        self.onetime_replication_tasks = {}
        self.vm_contexts = {}
        self.vmware_contexts = {}

    async def is_running(self):
        return await self.middleware.call("service.started", "zettarepl")

    def start(self):
        self._refresh_definition()
        self.middleware.call_sync("service.control", "START", "zettarepl")
        self._send_command({"command": "reload"}, require_running=False)

    def _refresh_definition(self):
        try:
            definition, hold_tasks = self.middleware.call_sync("zettarepl.build_definition")
        except Exception as e:
            self.logger.error("Error generating zettarepl definition", exc_info=True)
            self.middleware.call_sync("zettarepl.set_error", {
                "state": "ERROR",
                "datetime": utc_now(),
                "error": make_sentence(str(e)),
            })
            raise CallError(f"Internal error: {e!r}")

        self.middleware.call_sync("zettarepl.set_error", None)

        with self.lock:
            self.generation += 1
            self.definition = definition

        self.middleware.call_sync("zettarepl.notify_definition", definition, hold_tasks)

        return definition

    def _send_command(self, command, require_running=True):
        if require_running and not self.middleware.call_sync("zettarepl.is_running"):
            raise CallError("The zettarepl service is not running")

        self.middleware.send_event("zettarepl.command", "CHANGED", fields=command)

    def get_definition(self):
        if self.definition is None:
            self._refresh_definition()

        with self.lock:
            return {"generation": self.generation, "definition": self.definition}

    async def notify_definition_read(self, data):
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

        await self.middleware.call("zettarepl.set_definition_errors", definition_errors)

    def notify_status(self, data):
        self._fail_unfinished_tasks(DAEMON_RESTARTED_ERROR, set(data["running"]) | set(data["pending"]))

    def notify(self, notifications):
        for notification in notifications:
            try:
                self._process_notification(notification)
            except Exception:
                self.logger.warning("Unhandled exception processing %r", notification, exc_info=True)

    async def periodic_snapshot_task_start(self, task_id):
        await self.middleware.call("zettarepl.set_state", f"periodic_snapshot_{task_id}", {
            "state": "RUNNING",
            "datetime": utc_now(),
        })

        id_ = int(task_id.split("_")[-1])

        context = None
        if begin_context := await self.middleware.call("vmware.periodic_snapshot_task_begin", id_):
            context = await (
                await self.middleware.call("vmware.periodic_snapshot_task_proceed", begin_context)
            ).wait(raise_error=True)
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

    async def periodic_snapshot_task_end(self, task_id):
        id_ = int(task_id.split("_")[-1])

        context = self.vmware_contexts.pop(id_, None)
        vm_context = self.vm_contexts.pop(id_, None)

        if context:
            try:
                await (
                    await self.middleware.call("vmware.periodic_snapshot_task_end", context)
                ).wait(raise_error=True)
            except Exception:
                self.logger.error("Failed to finalize VMWare snapshot for task %r", task_id, exc_info=True)

        if vm_context:
            await self.middleware.call("vm.resume_suspended_vms", list(vm_context))

    def _fail_unfinished_tasks(self, error, alive):
        task_error_channels = [
            ("replication_", self.replication_jobs_channels,
             lambda task_id: ReplicationTaskError(task_id, error)),
            ("periodic_snapshot_", self.periodic_snapshot_task_jobs_channels,
             lambda task_id: PeriodicSnapshotTaskError(task_id, error)),
        ]
        for k, v in self.middleware.call_sync("zettarepl.get_state").get("tasks", {}).items():
            for prefix, channels, make_error in task_error_channels:
                if k.startswith(prefix) and v.get("state") in ("WAITING", "RUNNING"):
                    task_id = k[len(prefix):]
                    if task_id in alive:
                        continue

                    self.middleware.call_sync("zettarepl.set_state", k, {
                        "state": "ERROR",
                        "datetime": utc_now(),
                        "error": error,
                    })
                    for channel in channels[task_id]:
                        channel.put(make_error(task_id))

    def update_config(self, config):
        self.update_tasks()

    def update_tasks(self):
        try:
            self._refresh_definition()
        except CallError:
            return

        self._send_command({"command": "reload"}, require_running=False)

    def run_periodic_snapshot_task(self, id_):
        self._send_command({
            "command": "run_task",
            "class_name": "PeriodicSnapshotTask",
            "task_id": f"task_{id_}",
        })

        channels = self.periodic_snapshot_task_jobs_channels[f"task_{id_}"]
        channel = queue.Queue()
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

    def run_replication_task(self, id_, really_run, job):
        if really_run:
            self._send_command({
                "command": "run_task",
                "class_name": "ReplicationTask",
                "task_id": f"task_{id_}",
            })

        self._run_replication_task_job(f"task_{id_}", job)

    def run_onetime_replication_task(self, job, task):
        self.onetime_replication_tasks[job.id] = task
        try:
            self.update_tasks()

            state = self.middleware.call_sync("zettarepl.get_state")
            if "error" in state:
                raise CallError(state["error"])
            task_state = state["tasks"].get(f"job_{job.id}")
            if task_state:
                if task_state["state"] == "ERROR":
                    raise CallError(task_state["error"])
                if task_state["state"] == "HOLD":
                    raise CallError(task_state["reason"])
                if task_state["state"] != "WAITING":
                    raise CallError(task_state)

            self._send_command({
                "command": "run_task",
                "class_name": "ReplicationTask",
                "task_id": f"job_{job.id}",
            })

            self._run_replication_task_job(f"job_{job.id}", job)
        finally:
            self.onetime_replication_tasks.pop(job.id)
            self.update_tasks()

    def _run_replication_task_job(self, id_, job):
        channels = self.replication_jobs_channels[id_]
        channel = queue.Queue()
        channels.append(channel)
        snapshot_start_message = None
        snapshot_progress_message = None
        data_progress_message = None
        try:
            while True:
                message = channel.get()

                if isinstance(message, ReplicationTaskLog):
                    job.logs_fd.write(message.log.encode("utf8", "ignore") + b"\n")

                if isinstance(message, ReplicationTaskSnapshotStart):
                    snapshot_start_message = message
                    snapshot_progress_message = None
                    self._set_replication_task_progress(job, snapshot_start_message, snapshot_progress_message,
                                                        data_progress_message)

                if isinstance(message, ReplicationTaskSnapshotProgress):
                    snapshot_progress_message = message
                    self._set_replication_task_progress(job, snapshot_start_message, snapshot_progress_message,
                                                        data_progress_message)

                if isinstance(message, ReplicationTaskDataProgress):
                    data_progress_message = message
                    self._set_replication_task_progress(job, snapshot_start_message, snapshot_progress_message,
                                                        data_progress_message)

                if isinstance(message, ReplicationTaskSuccess):
                    return

                if isinstance(message, ReplicationTaskError):
                    raise CallError(make_sentence(message.error))
        finally:
            channels.remove(channel)

    def _set_replication_task_progress(self, job, snapshot_start_message, snapshot_progress_message,
                                       data_progress_message):
        if snapshot_start_message is None:
            return

        if snapshot_progress_message is None:
            message = snapshot_start_message
            progress = 100 * (message.snapshots_sent / message.snapshots_total)
            text = (
                f"Sending {message.snapshots_sent + 1} of {message.snapshots_total}: "
                f"{message.dataset}@{message.snapshot}"
            )
        else:
            message = snapshot_progress_message
            progress = 100 * (
                (message.snapshots_sent + message.bytes_sent / (message.bytes_total or float("inf"))) /
                message.snapshots_total
            )
            text = (
                f"Sending {message.snapshots_sent + 1} of {message.snapshots_total}: "
                f"{message.dataset}@{message.snapshot} ({format_size(message.bytes_sent)} / "
                f"{format_size(message.bytes_total)})"
            )

        if data_progress_message is not None:
            # Destination can result being larger than source
            # Do this to avoid displaying progress like "[total 11.11 TiB out of 11.04 TiB]"
            total = max(data_progress_message.dst_size, data_progress_message.src_size)
            text += (
                f" [total {format_size(data_progress_message.dst_size)} of "
                f"{format_size(total)}]"
            )

        job.set_progress(progress, text)

    async def list_datasets(self, transport, ssh_credentials=None):
        async with self._handle_ssh_exceptions():
            async with self._get_zettarepl_shell(transport, ssh_credentials) as shell:
                datasets = await self.middleware.run_in_thread(list_datasets, shell)

        return [
            ds
            for ds in datasets
            if not any(r.match(ds) for r in INVALID_DATASETS)
        ]

    async def create_dataset(self, dataset, transport, ssh_credentials=None):
        async with self._handle_ssh_exceptions():
            async with self._get_zettarepl_shell(transport, ssh_credentials) as shell:
                return await self.middleware.run_in_thread(create_dataset, shell, dataset)

    async def count_eligible_manual_snapshots(self, data):
        if data["naming_schema"] and data["name_regex"]:
            raise CallError("`naming_schema` and `name_regex` cannot be used simultaneously", errno.EINVAL)

        async with self._handle_ssh_exceptions():
            async with self._get_zettarepl_shell(data["transport"], data["ssh_credentials"]) as shell:
                snapshots = await self.middleware.run_in_thread(
                    multilist_snapshots, shell, [(dataset, False) for dataset in data["datasets"]]
                )

        if data["naming_schema"]:
            parsed = parse_snapshots_names_with_multiple_schemas([s.name for s in snapshots], data["naming_schema"])
        elif data["name_regex"]:
            try:
                name_pattern = compile_name_regex(data["name_regex"])
            except Exception as e:
                raise CallError(f"Invalid `name_regex`: {e}")

            parsed = [s.name for s in snapshots if name_pattern.match(s.name)]
        else:
            raise CallError("Either `naming_schema` or `name_regex` must be specified", errno.EINVAL)

        return {
            "total": len(snapshots),
            "eligible": len(parsed),
        }

    async def get_source_target_datasets_mapping(self, source_datasets, target_dataset):
        fake_replication_task = types.SimpleNamespace()
        fake_replication_task.source_datasets = source_datasets
        fake_replication_task.target_dataset = target_dataset
        return {
            source_dataset: get_target_dataset(fake_replication_task, source_dataset)
            for source_dataset in source_datasets
        }

    async def target_unmatched_snapshots(self, direction, source_datasets, target_dataset, transport, ssh_credentials):
        datasets = await self.get_source_target_datasets_mapping(source_datasets, target_dataset)

        try:
            local_shell = LocalShell()
            async with self._get_zettarepl_shell(transport, ssh_credentials) as remote_shell:
                if direction == "PUSH":
                    source_shell = local_shell
                    target_shell = remote_shell
                else:
                    source_shell = remote_shell
                    target_shell = local_shell

                target_datasets = set(await self.middleware.run_in_thread(list_datasets, target_shell))
                datasets = {source_dataset: target_dataset
                            for source_dataset, target_dataset in datasets.items()
                            if target_dataset in target_datasets}

                source_snapshots = group_snapshots_by_datasets(await self.middleware.run_in_thread(
                    multilist_snapshots, source_shell, [(dataset, False) for dataset in datasets.keys()]
                ))
                target_snapshots = group_snapshots_by_datasets(await self.middleware.run_in_thread(
                    multilist_snapshots, target_shell, [(dataset, False) for dataset in datasets.values()]
                ))
        except Exception as e:
            raise CallError(repr(e))

        errors = {}
        for source_dataset, target_dataset in datasets.items():
            unmatched_snapshots = list(set(target_snapshots.get(target_dataset, [])) -
                                       set(source_snapshots.get(source_dataset, [])))
            if unmatched_snapshots:
                errors[target_dataset] = unmatched_snapshots

        return errors

    async def build_definition(self):
        config = await self.middleware.call("replication.config.config")
        # Sanitize against a stale DB value left over from an upgrade (e.g. a
        # legacy alias like "Japan") -- the
        # ZoneInfo lookup downstream would otherwise raise ZoneInfoNotFoundError.
        timezone = effective_timezone(
            (await self.middleware.call("system.general.config"))["timezone"]
        )

        pools = {pool["name"]: pool for pool in await self.middleware.call("pool.query")}

        hold_tasks = {}

        periodic_snapshot_tasks = {}
        for periodic_snapshot_task in await self.call2(self.s.pool.snapshottask.query, [["enabled", "=", True]]):
            hold_task_reason = self._hold_task_reason(pools, periodic_snapshot_task.dataset)
            if hold_task_reason:
                hold_tasks[PERIODIC_SNAPSHOT_TASK_STATE.task_id(periodic_snapshot_task.id)] = hold_task_reason
                continue

            periodic_snapshot_tasks[f"task_{periodic_snapshot_task.id}"] = self.periodic_snapshot_task_definition(
                periodic_snapshot_task,
            )

        replication_tasks = {}
        for replication_task in await self.call2(self.s.replication.query):
            # `_replication_task_definition` builds a zettarepl-library task definition and is shared with one-time
            # tasks (`self.onetime_replication_tasks`), which are plain dicts of a different shape. Dump the model to
            # a dict here so both paths feed it the same representation.
            replication_task = replication_task.model_dump(expose_secrets=True)
            try:
                replication_tasks[f"task_{replication_task['id']}"] = await self._replication_task_definition(
                    pools, replication_task
                )
            except HoldReplicationTaskException as e:
                hold_tasks[REPLICATION_TASK_STATE.task_id(replication_task["id"])] = e.reason

        for job_id, replication_task in self.onetime_replication_tasks.items():
            try:
                replication_tasks[f"job_{job_id}"] = await self._replication_task_definition(pools, replication_task)
            except HoldReplicationTaskException as e:
                hold_tasks[f"job_{job_id}"] = e.reason

        definition = {
            "max-parallel-replication-tasks": config.max_parallel_replication_tasks,
            "timezone": timezone,
            "periodic-snapshot-tasks": periodic_snapshot_tasks,
            "replication-tasks": replication_tasks,
        }

        # Test if does not cause exceptions
        Definition.from_data(definition, raise_on_error=False)

        hold_tasks = {
            task_id: {
                "state": "HOLD",
                "datetime": utc_now(),
                "reason": make_sentence(reason),
            }
            for task_id, reason in hold_tasks.items()
        }

        return definition, hold_tasks

    def periodic_snapshot_task_definition(self, periodic_snapshot_task: PeriodicSnapshotTaskEntry):
        return {
            "dataset": periodic_snapshot_task.dataset,

            "recursive": periodic_snapshot_task.recursive,
            "exclude": periodic_snapshot_task.exclude,

            "lifetime": lifetime_iso8601(periodic_snapshot_task.lifetime_value,
                                         periodic_snapshot_task.lifetime_unit),

            "naming-schema": periodic_snapshot_task.naming_schema,

            "schedule": zettarepl_schedule(periodic_snapshot_task.schedule.model_dump()),

            "allow-empty": periodic_snapshot_task.allow_empty,
        }

    async def _replication_task_definition(self, pools, replication_task):
        if replication_task["direction"] == "PUSH":
            for source_dataset in replication_task["source_datasets"]:
                hold_task_reason = self._hold_task_reason(pools, source_dataset)
                if hold_task_reason:
                    raise HoldReplicationTaskException(hold_task_reason)

        if replication_task["direction"] == "PULL":
            hold_task_reason = self._hold_task_reason(pools, replication_task["target_dataset"])
            if hold_task_reason:
                raise HoldReplicationTaskException(hold_task_reason)

        if replication_task["transport"] != "LOCAL":
            if not await self.middleware.call("network.general.can_perform_activity", "replication"):
                raise HoldReplicationTaskException("Replication network activity is disabled")

        try:
            transport = await self._define_transport(
                replication_task["transport"],
                (replication_task["ssh_credentials"] or {}).get("id"),
                replication_task["netcat_active_side"],
                replication_task["netcat_active_side_listen_address"],
                replication_task["netcat_active_side_port_min"],
                replication_task["netcat_active_side_port_max"],
                replication_task["netcat_passive_side_connect_address"],
                replication_task["sudo"],
            )
        except CallError as e:
            raise HoldReplicationTaskException(e.errmsg)

        properties_exclude = replication_task["properties_exclude"].copy()
        properties_override = replication_task["properties_override"].copy()
        for property_ in ["mountpoint", "sharenfs", "sharesmb"]:
            if property_ == "mountpoint" and not replication_task.get("exclude_mountpoint_property", True):
                continue

            if property_ not in properties_override:
                if property_ not in properties_exclude:
                    properties_exclude.append(property_)

        definition = {
            "direction": replication_task["direction"].lower(),
            "transport": transport,
            "source-dataset": replication_task["source_datasets"],
            "target-dataset": replication_task["target_dataset"],
            "recursive": replication_task["recursive"],
            "exclude": replication_task_exclude(replication_task),
            "properties": replication_task["properties"],
            "properties-exclude": properties_exclude,
            "properties-override": properties_override,
            "replicate": replication_task["replicate"],
            "periodic-snapshot-tasks": [
                f"task_{periodic_snapshot_task['id']}"
                for periodic_snapshot_task in replication_task["periodic_snapshot_tasks"]
            ],
            "auto": replication_task["auto"] and replication_task["enabled"],
            "only-matching-schedule": replication_task["only_matching_schedule"] and replication_task["enabled"],
            "allow-from-scratch": replication_task["allow_from_scratch"],
            "only-from-scratch": replication_task.get("only_from_scratch", False),
            "readonly": replication_task["readonly"].lower(),
            "mount": replication_task.get("mount", True),
            "hold-pending-snapshots": replication_task["hold_pending_snapshots"],
            "retention-policy": replication_task["retention_policy"].lower(),
            "large-block": replication_task["large_block"],
            "embed": replication_task["embed"],
            "compressed": replication_task["compressed"],
            "retries": replication_task["retries"],
            "logging-level": (replication_task["logging_level"] or "NOTSET").lower(),
        }

        if replication_task["encryption"]:
            if replication_task["encryption_inherit"]:
                definition["encryption"] = "inherit"
            else:
                definition["encryption"] = {
                    "key": replication_task["encryption_key"],
                    "key-format": replication_task["encryption_key_format"].lower(),
                    "key-location": replication_task["encryption_key_location"],
                }
        if replication_task["naming_schema"]:
            definition["naming-schema"] = replication_task["naming_schema"]
        if replication_task["also_include_naming_schema"]:
            definition["also-include-naming-schema"] = replication_task["also_include_naming_schema"]
        if replication_task["name_regex"]:
            definition["name-regex"] = replication_task["name_regex"]
        if replication_task["schedule"] is not None and replication_task["enabled"]:
            definition["schedule"] = zettarepl_schedule(replication_task["schedule"])
        if replication_task["restrict_schedule"] is not None:
            definition["restrict-schedule"] = zettarepl_schedule(replication_task["restrict_schedule"])
        if replication_task["lifetime_value"] is not None and replication_task["lifetime_unit"] is not None:
            definition["lifetime"] = lifetime_iso8601(replication_task["lifetime_value"],
                                                      replication_task["lifetime_unit"])
        if replication_task["lifetimes"]:
            definition["lifetimes"] = {
                f"lifetime_{i}": {
                    "schedule": zettarepl_schedule(lifetime["schedule"]),
                    "lifetime": lifetime_iso8601(lifetime["lifetime_value"], lifetime["lifetime_unit"]),
                }
                for i, lifetime in enumerate(replication_task["lifetimes"])
            }
        if replication_task["compression"] is not None:
            definition["compression"] = replication_task["compression"].lower()
        if replication_task["speed_limit"] is not None:
            definition["speed-limit"] = replication_task["speed_limit"]

        return definition

    def _hold_task_reason(self, pools, dataset):
        pool = dataset.split("/")[0]

        if pool not in pools:
            return f"Pool {pool} does not exist"

        if pools[pool]["status"] == "OFFLINE":
            return f"Pool {pool} is offline"

    @asynccontextmanager
    async def _handle_ssh_exceptions(self):
        try:
            yield
        except paramiko.ssh_exception.BadHostKeyException as e:
            fingerprint = ":".join([hex(c)[2:] for c in e.key.get_fingerprint()])
            raise CallError(
                "Remote host identification has changed. Someone could be eavesdropping on you right now (man-in-the-"
                "middle attack)! It is also possible that a host key has just been changed. The fingerprint for the "
                f"RSA key sent by the remote host is {fingerprint}. Please edit your SSH connection and click "
                "\"Discover Remote Host Key\" to resolve this issue.",
                errno=errno.EACCES,
            )
        except (socket.timeout, paramiko.ssh_exception.NoValidConnectionsError, paramiko.ssh_exception.SSHException,
                IOError, OSError) as e:
            raise CallError(repr(e).replace("[Errno None] ", ""), errno=errno.EACCES)

    @asynccontextmanager
    async def _get_zettarepl_shell(self, transport, ssh_credentials):
        if transport != "LOCAL":
            await self.middleware.call("network.general.will_perform_activity", "replication")

        if transport == "SSH+NETCAT":
            # There is no difference shell-wise, but `_define_transport` for `SSH+NETCAT` will fail if we don't
            # supply `netcat_active_side` and other parameters which are totally unrelated here.
            transport = "SSH"

        transport_definition = await self._define_transport(transport, ssh_credentials)
        transport = create_transport(transport_definition)
        shell = transport.shell(transport)
        try:
            yield shell
        finally:
            await self.middleware.run_in_thread(shell.close)

    async def _define_transport(self, transport, ssh_credentials=None, netcat_active_side=None,
                                netcat_active_side_listen_address=None, netcat_active_side_port_min=None,
                                netcat_active_side_port_max=None, netcat_passive_side_connect_address=None,
                                sudo=False):

        if transport in ["SSH", "SSH+NETCAT"]:
            if ssh_credentials is None:
                raise CallError(f"You should pass SSH credentials for {transport} transport")

            ssh_credentials = await self.call2(self.s.keychaincredential.get_of_type, ssh_credentials,
                                               "SSH_CREDENTIALS")

            transport_definition = dict(type="ssh", **await self._define_ssh_transport(ssh_credentials), sudo=sudo)

            if transport == "SSH+NETCAT":
                transport_definition["type"] = "ssh+netcat"
                transport_definition["active-side"] = netcat_active_side.lower()
                if netcat_active_side_listen_address is not None:
                    transport_definition["active-side-listen-address"] = netcat_active_side_listen_address
                if netcat_active_side_port_min is not None:
                    transport_definition["active-side-min-port"] = netcat_active_side_port_min
                if netcat_active_side_port_max is not None:
                    transport_definition["active-side-max-port"] = netcat_active_side_port_max
                if netcat_passive_side_connect_address is not None:
                    transport_definition["passive-side-connect-address"] = netcat_passive_side_connect_address
        else:
            transport_definition = dict(type="local")

        return transport_definition

    async def _define_ssh_transport(self, credentials):
        attributes = credentials.attributes.get_secret_value()
        try:
            key_pair = await self.call2(self.s.keychaincredential.get_of_type,
                                        attributes.private_key, "SSH_KEY_PAIR")
        except CallError as e:
            raise CallError(f"Error while querying SSH key pair for credentials {credentials.id}: {e!s}")

        transport = {
            "hostname": attributes.host,
            "port": attributes.port,
            "username": attributes.username,
            "private-key": key_pair.attributes.get_secret_value().private_key,
            "host-key": attributes.remote_host_key,
            "connect-timeout": attributes.connect_timeout,
        }

        if (await self.call2(self.s.system.security.config)).enable_fips:
            transport["cipher"] = "fips"

        return transport

    def _process_notification(self, notification):
        message = ObserverMessage.load(notification)

        self.logger.trace("zettarepl notified %r", message)

        # Periodic snapshot task

        if isinstance(message, PeriodicSnapshotTaskSuccess):
            self.middleware.call_sync("zettarepl.set_last_snapshot", f"periodic_snapshot_{message.task_id}",
                                      f"{message.dataset}@{message.snapshot}")

            self.middleware.call_sync("zettarepl.set_state", f"periodic_snapshot_{message.task_id}", {
                "state": "FINISHED",
                "datetime": utc_now(),
            })

            for channel in self.periodic_snapshot_task_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, PeriodicSnapshotTaskError):
            self.middleware.call_sync("zettarepl.set_state", f"periodic_snapshot_{message.task_id}", {
                "state": "ERROR",
                "datetime": utc_now(),
                "error": make_sentence(message.error),
            })

            for channel in self.periodic_snapshot_task_jobs_channels[message.task_id]:
                channel.put(message)

        # Replication task events

        if isinstance(message, ReplicationTaskScheduled):
            if (
                    (self.middleware.call_sync(
                        "zettarepl.get_state_internal", f"replication_{message.task_id}"
                    ) or {}).get("state") != "RUNNING"
            ):
                self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                    "state": "WAITING",
                    "datetime": utc_now(),
                    "reason": message.waiting_reason,
                })

        if isinstance(message, ReplicationTaskStart):
            self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                "state": "RUNNING",
                "datetime": utc_now(),
            })

            # Start fake job if none are already running
            if not self.replication_jobs_channels[message.task_id]:
                self.call_sync2(self.s.replication.run, int(message.task_id[5:]),
                                ReplicationRunOptions(really_run=False))

        if isinstance(message, ReplicationTaskLog):
            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, ReplicationTaskSnapshotStart):
            self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
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
                }
            })

            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, ReplicationTaskSnapshotProgress):
            self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
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
                }
            })

            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, ReplicationTaskSnapshotSuccess):
            self.middleware.call_sync("zettarepl.set_last_snapshot", f"replication_{message.task_id}",
                                      f"{message.dataset}@{message.snapshot}")

            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, ReplicationTaskDataProgress):
            task_id = f"replication_{message.task_id}"
            try:
                state = self.middleware.call_sync("zettarepl.get_internal_task_state", task_id)
            except KeyError:
                pass
            else:
                if state["state"] == "RUNNING" and "progress" in state:
                    state["progress"].update({
                        "root_dataset": message.dataset,
                        "src_size": message.src_size,
                        "dst_size": message.dst_size,
                    })
                    self.middleware.call_sync("zettarepl.set_state", task_id, state)

            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, ReplicationTaskSuccess):
            self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                "state": "FINISHED",
                "datetime": utc_now(),
                "warnings": message.warnings,
            })

            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

        if isinstance(message, ReplicationTaskError):
            self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                "state": "ERROR",
                "datetime": utc_now(),
                "error": make_sentence(message.error),
            })

            for channel in self.replication_jobs_channels[message.task_id]:
                channel.put(message)

    async def terminate(self):
        await self.middleware.call("zettarepl.flush_state")
        await (await self.middleware.call("service.control", "STOP", "zettarepl")).wait()


async def pool_configuration_change(middleware, *args, **kwargs):
    await middleware.call("zettarepl.update_tasks")


async def setup(middleware):
    middleware.event_register("zettarepl.command", "Sent to the zettarepl service to control it.", private=True)

    await middleware.call("zettarepl.load_state")

    try:
        await middleware.call("zettarepl.start")
    except Exception:
        middleware.logger.error("Unhandled exception during zettarepl startup", exc_info=True)

    middleware.register_hook("pool.post_import", pool_configuration_change, sync=True)
    middleware.register_hook("pool.post_export", pool_configuration_change, sync=True)

    middleware.register_hook("pool.post_lock", pool_configuration_change, sync=True)
    middleware.register_hook("pool.post_unlock", pool_configuration_change, sync=True)

    middleware.register_hook("pool.post_create_or_update", pool_configuration_change, sync=True)
