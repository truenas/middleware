from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, time as _time, timedelta
import errno
import logging
import multiprocessing
import os
import pytz
import queue
import re
import setproctitle
import signal
import socket
import threading
import time
import types

import humanfriendly
import paramiko.ssh_exception

from zettarepl.dataset.create import create_dataset
from zettarepl.dataset.list import list_datasets
from zettarepl.definition.definition import (
    DefinitionErrors, PeriodicSnapshotTaskDefinitionError, ReplicationTaskDefinitionError, Definition
)
from zettarepl.observer import (
    PeriodicSnapshotTaskStart, PeriodicSnapshotTaskSuccess, PeriodicSnapshotTaskError,
    ReplicationTaskScheduled, ReplicationTaskStart, ReplicationTaskSnapshotStart, ReplicationTaskSnapshotProgress,
    ReplicationTaskSnapshotSuccess,
    ReplicationTaskDataProgress, ReplicationTaskSuccess, ReplicationTaskError,
)
from zettarepl.replication.task.dataset import get_target_dataset
from zettarepl.snapshot.list import multilist_snapshots, group_snapshots_by_datasets
from zettarepl.snapshot.name import parse_snapshots_names_with_multiple_schemas
from zettarepl.transport.create import create_transport
from zettarepl.transport.interface import ExecException
from zettarepl.transport.local import LocalShell
from zettarepl.transport.zfscli import get_properties_recursive
from zettarepl.utils.logging import (
    LongStringsFilter, ReplicationTaskLoggingLevelFilter, logging_record_replication_task
)
from zettarepl.zettarepl import create_zettarepl

from middlewared.client import Client, ClientException
from middlewared.logger import reconfigure_logging, setup_logging
from middlewared.service import CallError, Service
from middlewared.utils import start_daemon_thread
from middlewared.utils.cgroups import move_to_root_cgroups
import middlewared.utils.osc as osc
from middlewared.utils.string import make_sentence

INVALID_DATASETS = (
    re.compile(r"boot-pool($|/)"),
    re.compile(r"freenas-boot($|/)"),
    re.compile(r"[^/]+/\.system($|/)")
)


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
        if isinstance(schedule[k], _time):
            schedule[k] = str(schedule[k])[:5]

    return schedule


class HoldReplicationTaskException(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__()


class ReplicationTaskLog:
    def __init__(self, task_id, log):
        self.task_id = task_id
        self.log = log


class ObserverQueueLoggingHandler(logging.Handler):
    def __init__(self, observer_queue):
        self.observer_queue = observer_queue
        super().__init__()

    def emit(self, record):
        replication_task_id = logging_record_replication_task(record)
        if replication_task_id is not None:
            self.observer_queue.put(ReplicationTaskLog(replication_task_id, self.format(record)))


class ZettareplProcess:
    def __init__(self, definition, debug_level, log_handler, command_queue, observer_queue):
        self.definition = definition
        self.debug_level = debug_level
        self.log_handler = log_handler
        self.command_queue = command_queue
        self.observer_queue = observer_queue

        self.zettarepl = None

        self.vmware_contexts = {}

    def __call__(self):
        setproctitle.setproctitle('middlewared (zettarepl)')
        osc.die_with_parent()
        move_to_root_cgroups(os.getpid())
        if logging.getLevelName(self.debug_level) == logging.TRACE:
            # If we want TRACE then we want all debug from zettarepl
            default_level = logging.DEBUG
        elif logging.getLevelName(self.debug_level) == logging.DEBUG:
            # Regular development level. We don't need verbose debug from zettarepl
            default_level = logging.INFO
        else:
            default_level = logging.getLevelName(self.debug_level)
        setup_logging("", "DEBUG", self.log_handler)
        oqlh = ObserverQueueLoggingHandler(self.observer_queue)
        oqlh.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)-8s [%(threadName)s] [%(name)s] %(message)s',
                                            '%Y/%m/%d %H:%M:%S'))
        logging.getLogger("zettarepl").addHandler(oqlh)
        for handler in logging.getLogger("zettarepl").handlers:
            handler.addFilter(LongStringsFilter())
            handler.addFilter(ReplicationTaskLoggingLevelFilter(default_level))

        c = Client('ws+unix:///var/run/middlewared-internal.sock', py_exceptions=True)
        c.subscribe('core.reconfigure_logging', lambda *args, **kwargs: reconfigure_logging())

        definition = Definition.from_data(self.definition, raise_on_error=False)
        self.observer_queue.put(DefinitionErrors(definition.errors))

        self.zettarepl = create_zettarepl(definition)
        self.zettarepl.set_observer(self._observer)
        self.zettarepl.set_tasks(definition.tasks)

        start_daemon_thread(target=self._process_command_queue)

        while True:
            try:
                self.zettarepl.run()
            except Exception:
                logging.getLogger("zettarepl").error("Unhandled exception", exc_info=True)
                time.sleep(10)

    def _observer(self, message):
        self.observer_queue.put(message)

        logger = logging.getLogger("middlewared.plugins.zettarepl")

        try:
            if isinstance(message, (PeriodicSnapshotTaskStart, PeriodicSnapshotTaskSuccess, PeriodicSnapshotTaskError)):
                task_id = int(message.task_id.split("_")[-1])

                if isinstance(message, PeriodicSnapshotTaskStart):
                    with Client() as c:
                        context = None
                        if begin_context := c.call("vmware.periodic_snapshot_task_begin", task_id):
                            context = c.call("vmware.periodic_snapshot_task_proceed", begin_context, job=True)

                    self.vmware_contexts[task_id] = context

                    if context and context["vmsynced"]:
                        # If there were no failures and we successfully took some VMWare snapshots
                        # set the ZFS property to show the snapshot has consistent VM snapshots
                        # inside it.
                        return message.response(properties={"freenas:vmsynced": "Y"})

                if isinstance(message, (PeriodicSnapshotTaskSuccess, PeriodicSnapshotTaskError)):
                    context = self.vmware_contexts.pop(task_id, None)
                    if context:
                        with Client() as c:
                            c.call("vmware.periodic_snapshot_task_end", context, job=True)

        except ClientException as e:
            if e.error:
                logger.error("Unhandled exception in ZettareplProcess._observer: %r", e.error)
            if e.trace:
                logger.error("Unhandled exception in ZettareplProcess._observer:\n%s", e.trace["formatted"])
        except Exception:
            logger.error("Unhandled exception in ZettareplProcess._observer", exc_info=True)

    def _process_command_queue(self):
        logger = logging.getLogger("middlewared.plugins.zettarepl")

        while self.zettarepl is not None:
            command, args = self.command_queue.get()
            if command == "config":
                if "max_parallel_replication_tasks" in args:
                    self.zettarepl.max_parallel_replication_tasks = args["max_parallel_replication_tasks"]
                if "timezone" in args:
                    self.zettarepl.scheduler.tz_clock.timezone = pytz.timezone(args["timezone"])
            if command == "tasks":
                definition = Definition.from_data(args, raise_on_error=False)
                self.observer_queue.put(DefinitionErrors(definition.errors))
                self.zettarepl.set_tasks(definition.tasks)
            if command == "run_task":
                class_name, task_id = args
                for task in self.zettarepl.tasks:
                    if task.__class__.__name__ == class_name and task.id == task_id:
                        logger.debug("Running task %r", task)
                        self.zettarepl.scheduler.interrupt([task])
                        break
                else:
                    logger.warning("Task %s(%r) not found", class_name, task_id)
                    self.observer_queue.put(ReplicationTaskError(task_id, "Task not found"))


class ZettareplService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lock = threading.Lock()
        self.command_queue = None
        self.observer_queue = multiprocessing.Queue()
        self.observer_queue_reader = None
        self.replication_jobs_channels = defaultdict(list)
        self.onetime_replication_tasks = {}
        self.queue = None
        self.process = None
        self.zettarepl = None

    def is_running(self):
        return self.process is not None and self.process.is_alive()

    def start(self):
        try:
            definition, hold_tasks = self.middleware.call_sync("zettarepl.get_definition")
        except Exception as e:
            self.logger.error("Error generating zettarepl definition", exc_info=True)
            self.middleware.call_sync("zettarepl.set_error", {
                "state": "ERROR",
                "datetime": datetime.utcnow(),
                "error": make_sentence(str(e)),
            })
            raise CallError(f"Internal error: {e!r}")
        else:
            self.middleware.call_sync("zettarepl.set_error", None)

        with self.lock:
            if not self.is_running():
                self.queue = multiprocessing.Queue()
                self.process = multiprocessing.Process(
                    name="zettarepl",
                    target=ZettareplProcess(definition, self.middleware.debug_level, self.middleware.log_handler,
                                            self.queue, self.observer_queue)
                )
                self.process.start()
                start_daemon_thread(target=self._join, args=(self.process,))

                if self.observer_queue_reader is None:
                    self.observer_queue_reader = start_daemon_thread(target=self._observer_queue_reader)

                self.middleware.call_sync("zettarepl.notify_definition", definition, hold_tasks)

    def stop(self):
        with self.lock:
            if self.process:
                self.process.terminate()
                event = threading.Event()

                def target():
                    try:
                        os.waitpid(self.process.pid, 0)
                    except ChildProcessError:
                        pass
                    event.set()

                start_daemon_thread(target=target)
                if not event.wait(5):
                    self.logger.warning("Zettarepl was not joined in time, sending SIGKILL")
                    os.kill(self.process.pid, signal.SIGKILL)

                self.process = None

    def _join(self, process):
        process.join()

        restart = False
        with self.lock:
            if process == self.process:
                restart = True

        if restart:
            self.logger.error("Abnormal zettarepl process termination with code %r, restarting", process.exitcode)
            for k, v in self.middleware.call_sync("zettarepl.get_state").get("tasks", {}).items():
                if k.startswith("replication_") and v.get("state") in ("WAITING", "RUNNING"):
                    error = f"Abnormal zettarepl process termination with code {process.exitcode}."
                    self.middleware.call_sync("zettarepl.set_state", k, {
                        "state": "ERROR",
                        "datetime": datetime.utcnow(),
                        "error": error,
                    })
                    task_id = k[len("replication_"):]
                    for channel in self.replication_jobs_channels[task_id]:
                        channel.put(ReplicationTaskError(task_id, error))
            self.middleware.call_sync("zettarepl.start")

    def update_config(self, config):
        if self.queue:
            self.queue.put(("config", config))

    def update_tasks(self):
        try:
            definition, hold_tasks = self.middleware.call_sync("zettarepl.get_definition")
        except Exception as e:
            self.logger.error("Error generating zettarepl definition", exc_info=True)
            self.middleware.call_sync("zettarepl.set_error", {
                "state": "ERROR",
                "datetime": datetime.utcnow(),
                "error": make_sentence(str(e)),
            })
            return
        else:
            self.middleware.call_sync("zettarepl.set_error", None)

        if self._is_empty_definition(definition):
            self.middleware.call_sync("zettarepl.stop")
        else:
            self.middleware.call_sync("zettarepl.start")
            self.queue.put(("tasks", definition))

        self.middleware.call_sync("zettarepl.notify_definition", definition, hold_tasks)

    async def run_periodic_snapshot_task(self, id):
        try:
            self.queue.put(("run_task", ("PeriodicSnapshotTask", f"task_{id}")))
        except Exception:
            raise CallError("Replication service is not running")

    def run_replication_task(self, id, really_run, job):
        if really_run:
            try:
                self.queue.put(("run_task", ("ReplicationTask", f"task_{id}")))
            except Exception:
                raise CallError("Replication service is not running")

        self._run_replication_task_job(f"task_{id}", job)

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

            self.queue.put(("run_task", ("ReplicationTask", f"job_{job.id}")))

            self._run_replication_task_job(f"job_{job.id}", job)
        finally:
            self.onetime_replication_tasks.pop(job.id)
            self.update_tasks()

    def _run_replication_task_job(self, id, job):
        channels = self.replication_jobs_channels[id]
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
                f"{message.dataset}@{message.snapshot} ({humanfriendly.format_size(message.bytes_sent, binary=True)} / "
                f"{humanfriendly.format_size(message.bytes_total, binary=True)})"
            )

        if data_progress_message is not None:
            text += (
                f" [total {humanfriendly.format_size(data_progress_message.dst_size, binary=True)} of "
                f"{humanfriendly.format_size(data_progress_message.src_size, binary=True)}]"
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

    async def count_eligible_manual_snapshots(self, datasets, naming_schemas, transport, ssh_credentials=None):
        async with self._handle_ssh_exceptions():
            async with self._get_zettarepl_shell(transport, ssh_credentials) as shell:
                snapshots = await self.middleware.run_in_thread(
                    multilist_snapshots, shell, [(dataset, False) for dataset in datasets]
                )

        parsed = parse_snapshots_names_with_multiple_schemas([s.name for s in snapshots], naming_schemas)

        return {
            "total": len(snapshots),
            "eligible": len(parsed),
        }

    async def target_unmatched_snapshots(self, direction, source_datasets, target_dataset, transport, ssh_credentials):
        fake_replication_task = types.SimpleNamespace()
        fake_replication_task.source_datasets = source_datasets
        fake_replication_task.target_dataset = target_dataset
        datasets = {source_dataset: get_target_dataset(fake_replication_task, source_dataset)
                    for source_dataset in source_datasets}

        try:
            local_shell = LocalShell()
            async with self._get_zettarepl_shell(transport, ssh_credentials) as remote_shell:
                if direction == "PUSH":
                    source_shell = local_shell
                    target_shell = remote_shell
                else:
                    source_shell = remote_shell
                    target_shell = local_shell

                target_datasets = set(list_datasets(target_shell))
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

    async def datasets_have_encryption(self, datasets, recursive, transport, ssh_credentials=None):
        async with self._handle_ssh_exceptions():
            async with self._get_zettarepl_shell(transport, ssh_credentials) as shell:
                try:
                    properties_result = await self.middleware.run_in_thread(
                        get_properties_recursive, shell, datasets, {"encryption": str}, recursive=recursive,
                    )
                except ExecException as e:
                    self.middleware.logger.debug("Encryption not supported on shell %r: %r (exit code = %d)",
                                                 shell, e.stdout.split("\n")[0], e.returncode)
                    return []

        result = []
        for dataset, properties in properties_result.items():
            if properties["encryption"] != "off":
                if any(dataset.startswith(f"{parent}/") for parent in result):
                    continue

                result.append(dataset)

        return result

    async def get_definition(self):
        config = await self.middleware.call("replication.config.config")
        timezone = (await self.middleware.call("system.general.config"))["timezone"]

        pools = {pool["name"]: pool for pool in await self.middleware.call("pool.query")}

        hold_tasks = {}

        periodic_snapshot_tasks = {}
        for periodic_snapshot_task in await self.middleware.call("pool.snapshottask.query", [["enabled", "=", True]]):
            hold_task_reason = self._hold_task_reason(pools, periodic_snapshot_task["dataset"])
            if hold_task_reason:
                hold_tasks[f"periodic_snapshot_task_{periodic_snapshot_task['id']}"] = hold_task_reason
                continue

            periodic_snapshot_tasks[f"task_{periodic_snapshot_task['id']}"] = self.periodic_snapshot_task_definition(
                periodic_snapshot_task,
            )

        replication_tasks = {}
        for replication_task in await self.middleware.call("replication.query", [["enabled", "=", True]]):
            try:
                replication_tasks[f"task_{replication_task['id']}"] = await self._replication_task_definition(
                    pools, replication_task
                )
            except HoldReplicationTaskException as e:
                hold_tasks[f"replication_task_{replication_task['id']}"] = e.reason

        for job_id, replication_task in self.onetime_replication_tasks.items():
            try:
                replication_tasks[f"job_{job_id}"] = await self._replication_task_definition(pools, replication_task)
            except HoldReplicationTaskException as e:
                hold_tasks[f"job_{job_id}"] = e.reason

        definition = {
            "max-parallel-replication-tasks": config["max_parallel_replication_tasks"],
            "timezone": timezone,
            "use-removal-dates": True,
            "periodic-snapshot-tasks": periodic_snapshot_tasks,
            "replication-tasks": replication_tasks,
        }

        # Test if does not cause exceptions
        Definition.from_data(definition, raise_on_error=False)

        hold_tasks = {
            task_id: {
                "state": "HOLD",
                "datetime": datetime.utcnow(),
                "reason": make_sentence(reason),
            }
            for task_id, reason in hold_tasks.items()
        }

        return definition, hold_tasks

    def periodic_snapshot_task_definition(self, periodic_snapshot_task):
        return {
            "dataset": periodic_snapshot_task["dataset"],

            "recursive": periodic_snapshot_task["recursive"],
            "exclude": periodic_snapshot_task["exclude"],

            "lifetime": lifetime_iso8601(periodic_snapshot_task["lifetime_value"],
                                         periodic_snapshot_task["lifetime_unit"]),

            "naming-schema": periodic_snapshot_task["naming_schema"],

            "schedule": zettarepl_schedule(periodic_snapshot_task["schedule"]),

            "allow-empty": periodic_snapshot_task["allow_empty"],
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
            )
        except CallError as e:
            raise HoldReplicationTaskException(e.errmsg)

        properties_exclude = replication_task["properties_exclude"].copy()
        properties_override = replication_task["properties_override"].copy()
        for property in ["mountpoint", "sharenfs", "sharesmb"]:
            if property not in properties_override:
                if property not in properties_exclude:
                    properties_exclude.append(property)

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
            "auto": replication_task["auto"],
            "only-matching-schedule": replication_task["only_matching_schedule"],
            "allow-from-scratch": replication_task["allow_from_scratch"],
            "readonly": replication_task["readonly"].lower(),
            "hold-pending-snapshots": replication_task["hold_pending_snapshots"],
            "retention-policy": replication_task["retention_policy"].lower(),
            "large-block": replication_task["large_block"],
            "embed": replication_task["embed"],
            "compressed": replication_task["compressed"],
            "retries": replication_task["retries"],
            "logging-level": (replication_task["logging_level"] or "NOTSET").lower(),
        }

        if replication_task["encryption"]:
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
        if replication_task["schedule"] is not None:
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

        if not pools[pool]["is_decrypted"]:
            return f"Pool {pool} is locked"

    @asynccontextmanager
    async def _handle_ssh_exceptions(self):
        try:
            yield
        except (socket.timeout, paramiko.ssh_exception.NoValidConnectionsError, paramiko.ssh_exception.SSHException,
                IOError, OSError) as e:
            raise CallError(repr(e).replace("[Errno None] ", ""), errno=errno.EACCES)

    @asynccontextmanager
    async def _get_zettarepl_shell(self, transport, ssh_credentials):
        if transport != "LOCAL":
            await self.middleware.call("network.general.will_perform_activity", "replication")

        transport_definition = await self._define_transport(transport, ssh_credentials)
        transport = create_transport(transport_definition)
        shell = transport.shell(transport)
        try:
            yield shell
        finally:
            await self.middleware.run_in_thread(shell.close)

    async def _define_transport(self, transport, ssh_credentials=None, netcat_active_side=None,
                                netcat_active_side_listen_address=None, netcat_active_side_port_min=None,
                                netcat_active_side_port_max=None, netcat_passive_side_connect_address=None):

        if transport in ["SSH", "SSH+NETCAT"]:
            if ssh_credentials is None:
                raise CallError(f"You should pass SSH credentials for {transport} transport")

            ssh_credentials = await self.middleware.call("keychaincredential.get_of_type", ssh_credentials,
                                                         "SSH_CREDENTIALS")

            transport_definition = dict(type="ssh", **await self._define_ssh_transport(ssh_credentials))

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
        try:
            key_pair = await self.middleware.call("keychaincredential.get_of_type",
                                                  credentials["attributes"]["private_key"], "SSH_KEY_PAIR")
        except CallError as e:
            raise CallError(f"Error while querying SSH key pair for credentials {credentials['id']}: {e!s}")

        return {
            "hostname": credentials["attributes"]["host"],
            "port": credentials["attributes"]["port"],
            "username": credentials["attributes"]["username"],
            "private-key": key_pair["attributes"]["private_key"],
            "host-key": credentials["attributes"]["remote_host_key"],
            "connect-timeout": credentials["attributes"]["connect_timeout"],
        }

    def _is_empty_definition(self, definition):
        return not definition["periodic-snapshot-tasks"] and not definition["replication-tasks"]

    def _observer_queue_reader(self):
        while True:
            message = self.observer_queue.get()

            try:
                self.logger.trace("Observer queue got %r", message)

                # Global events

                if isinstance(message, DefinitionErrors):
                    definition_errors = {}
                    for error in message.errors:
                        if isinstance(error, PeriodicSnapshotTaskDefinitionError):
                            definition_errors[f"periodic_snapshot_{error.task_id}"] = {
                                "state": "ERROR",
                                "datetime": datetime.utcnow(),
                                "error": make_sentence(str(error)),
                            }
                        if isinstance(error, ReplicationTaskDefinitionError):
                            definition_errors[f"replication_{error.task_id}"] = {
                                "state": "ERROR",
                                "datetime": datetime.utcnow(),
                                "error": make_sentence(str(error)),
                            }

                    self.middleware.call_sync("zettarepl.set_definition_errors", definition_errors)

                # Periodic snapshot task

                if isinstance(message, PeriodicSnapshotTaskStart):
                    self.middleware.call_sync("zettarepl.set_state", f"periodic_snapshot_{message.task_id}", {
                        "state": "RUNNING",
                        "datetime": datetime.utcnow(),
                    })

                if isinstance(message, PeriodicSnapshotTaskSuccess):
                    self.middleware.call_sync("zettarepl.set_state", f"periodic_snapshot_{message.task_id}", {
                        "state": "FINISHED",
                        "datetime": datetime.utcnow(),
                    })

                if isinstance(message, PeriodicSnapshotTaskError):
                    self.middleware.call_sync("zettarepl.set_state", f"periodic_snapshot_{message.task_id}", {
                        "state": "ERROR",
                        "datetime": datetime.utcnow(),
                        "error": make_sentence(message.error),
                    })

                # Replication task events

                if isinstance(message, ReplicationTaskScheduled):
                    if (
                            (self.middleware.call_sync(
                                "zettarepl.get_state_internal", f"replication_{message.task_id}"
                            ) or {}).get("state") != "RUNNING"
                    ):
                        self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                            "state": "WAITING",
                            "datetime": datetime.utcnow(),
                        })

                if isinstance(message, ReplicationTaskStart):
                    self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                        "state": "RUNNING",
                        "datetime": datetime.utcnow(),
                    })

                    # Start fake job if none are already running
                    if not self.replication_jobs_channels[message.task_id]:
                        self.middleware.call_sync("replication.run", int(message.task_id[5:]), False)

                if isinstance(message, ReplicationTaskLog):
                    for channel in self.replication_jobs_channels[message.task_id]:
                        channel.put(message)

                if isinstance(message, ReplicationTaskSnapshotStart):
                    self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                        "state": "RUNNING",
                        "datetime": datetime.utcnow(),
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
                        "datetime": datetime.utcnow(),
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
                        "datetime": datetime.utcnow(),
                        "warnings": message.warnings,
                    })

                    for channel in self.replication_jobs_channels[message.task_id]:
                        channel.put(message)

                if isinstance(message, ReplicationTaskError):
                    self.middleware.call_sync("zettarepl.set_state", f"replication_{message.task_id}", {
                        "state": "ERROR",
                        "datetime": datetime.utcnow(),
                        "error": make_sentence(message.error),
                    })

                    for channel in self.replication_jobs_channels[message.task_id]:
                        channel.put(message)

            except Exception:
                self.logger.warning("Unhandled exception in observer_queue_reader", exc_info=True)

    async def terminate(self):
        await self.middleware.call("zettarepl.flush_state")
        await self.middleware.run_in_thread(self.stop)


async def pool_configuration_change(middleware, *args, **kwargs):
    await middleware.call("zettarepl.update_tasks")


async def setup(middleware):
    await middleware.call("zettarepl.load_state")

    try:
        await middleware.call("zettarepl.start")
    except Exception:
        pass

    middleware.register_hook("pool.post_import", pool_configuration_change, sync=True)
    middleware.register_hook("pool.post_export", pool_configuration_change, sync=True)

    middleware.register_hook("pool.post_lock", pool_configuration_change, sync=True)
    middleware.register_hook("pool.post_unlock", pool_configuration_change, sync=True)

    middleware.register_hook("pool.post_create_or_update", pool_configuration_change, sync=True)
