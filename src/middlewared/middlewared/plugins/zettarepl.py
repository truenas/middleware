from datetime import datetime, timedelta
import logging
import multiprocessing
import os
import pytz
import signal
import threading
import time

from zettarepl.dataset.create import create_dataset
from zettarepl.dataset.list import list_datasets
from zettarepl.definition.definition import Definition
from zettarepl.observer import *
from zettarepl.scheduler.clock import Clock
from zettarepl.scheduler.scheduler import Scheduler
from zettarepl.scheduler.tz_clock import TzClock
from zettarepl.transport.create import create_transport
from zettarepl.transport.local import LocalShell
from zettarepl.zettarepl import Zettarepl

from middlewared.logger import setup_logging
from middlewared.service import CallError, Service
from middlewared.utils import start_daemon_thread

SCAN_THREADS = {}


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


def zettarepl_schedule(schedule):
    schedule = {k.replace("_", "-"): v for k, v in schedule.items()}
    schedule["day-of-month"] = schedule.pop("dom")
    schedule["day-of-week"] = schedule.pop("dow")
    return schedule


class ZettareplProcess:
    def __init__(self, definition, debug_level, log_handler, command_queue, observer_queue):
        self.definition = definition
        self.debug_level = debug_level
        self.log_handler = log_handler
        self.command_queue = command_queue
        self.observer_queue = observer_queue

        self.zettarepl = None

    def __call__(self):
        if logging.getLevelName(self.debug_level) == logging.TRACE:
            # If we want TRACE then we want all debug from zettarepl
            debug_level = "DEBUG"
        elif logging.getLevelName(self.debug_level) == logging.DEBUG:
            # Regular development level. We don't need verbose debug from zettarepl
            debug_level = "INFO"
        else:
            debug_level = self.debug_level
        setup_logging("zettarepl", debug_level, self.log_handler)

        definition = Definition.from_data(self.definition)

        clock = Clock()
        tz_clock = TzClock(definition.timezone, clock.now)

        scheduler = Scheduler(clock, tz_clock)
        local_shell = LocalShell()

        self.zettarepl = Zettarepl(scheduler, local_shell)
        self.zettarepl.set_observer(self.observer_queue.put)
        self.zettarepl.set_tasks(definition.tasks)

        start_daemon_thread(self._process_command_queue)

        while True:
            try:
                self.zettarepl.run()
            except Exception:
                logging.getLogger("zettarepl").error("Unhandled exception", exc_info=True)
                time.sleep(10)

    def _process_command_queue(self):
        while self.zettarepl is not None:
            command, args = self.command_queue.get()
            if command == "timezone":
                self.zettarepl.scheduler.tz_clock.timezone = pytz.timezone(args)
            if command == "tasks":
                self.zettarepl.set_tasks(Definition.from_data(args).tasks)


class ZettareplService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lock = threading.Lock()
        self.command_queue = None
        self.observer_queue = multiprocessing.Queue()
        self.observer_queue_reader = None
        self.state = {}
        self.last_snapshot = {}
        self.queue = None
        self.process = None
        self.zettarepl = None

    def is_running(self):
        return self.process is not None and self.process.is_alive()

    def get_state(self):
        return {
            k: (
                dict(v, last_snapshot=self.last_snapshot.get(k))
                if k.startswith("replication_task_")
                else v
            )
            for k, v in self.state.items()
        }

    def start(self, definition=None):
        if definition is None:
            try:
                definition = self.middleware.call_sync("zettarepl.get_definition")
            except Exception as e:
                self.logger.error("Error generating zettarepl definition", exc_info=True)
                raise CallError(f"Internal error: {e!r}")

        with self.lock:
            if not self.is_running():
                self.queue = multiprocessing.Queue()
                self.process = multiprocessing.Process(
                    name="zettarepl",
                    target=ZettareplProcess(definition, self.middleware.debug_level, self.middleware.log_handler,
                                            self.queue, self.observer_queue)
                )
                self.process.start()

                if self.observer_queue_reader is None:
                    self.observer_queue_reader = start_daemon_thread(self._observer_queue_reader, daemon=True)

    def stop(self):
        with self.lock:
            if self.process:
                self.process.terminate()
                self.process.join(5)

                if self.process.is_alive():
                    self.logger.warning("Zettarepl was not joined in time, sending SIGKILL")
                    os.kill(self.process.pid, signal.SIGKILL)

                self.process = None

    def update_timezone(self, timezone):
        if self.queue:
            self.queue.put(("timezone", timezone))

    def update_tasks(self):
        try:
            definition = self.middleware.call_sync("zettarepl.get_definition")
        except Exception:
            self.logger.error("Error generating zettarepl definition", exc_info=True)
            return

        if self._is_empty_definition(definition):
            self.middleware.call_sync("zettarepl.stop")
        else:
            self.middleware.call_sync("zettarepl.start")
            self.queue.put(("tasks", definition))

    async def list_datasets(self, transport, ssh_credentials=None):
        try:
            return list_datasets(await self._get_zettarepl_shell(transport, ssh_credentials))
        except Exception as e:
            raise CallError(repr(e))

    async def create_dataset(self, dataset, transport, ssh_credentials=None):
        try:
            return create_dataset(await self._get_zettarepl_shell(transport, ssh_credentials), dataset)
        except Exception as e:
            raise CallError(repr(e))

    async def get_definition(self):
        timezone = (await self.middleware.call("system.general.config"))["timezone"]

        periodic_snapshot_tasks = {}
        for periodic_snapshot_task in await self.middleware.call("pool.snapshottask.query", [["enabled", "=", True],
                                                                                             ["legacy", "=", False]]):
            periodic_snapshot_tasks[f"task_{periodic_snapshot_task['id']}"] = {
                "dataset": periodic_snapshot_task["dataset"],

                "recursive": periodic_snapshot_task["recursive"],
                "exclude": periodic_snapshot_task["exclude"],

                "lifetime": lifetime_iso8601(periodic_snapshot_task["lifetime_value"],
                                             periodic_snapshot_task["lifetime_unit"]),

                "naming-schema": periodic_snapshot_task["naming_schema"],

                "schedule": zettarepl_schedule(periodic_snapshot_task["schedule"]),
            }

        replication_tasks = {}
        legacy_periodic_snapshot_tasks_ids = {
            periodic_snapshot_task["id"]
            for periodic_snapshot_task in await self.middleware.call("pool.snapshottask.query", [["legacy", "=", True]])
        }
        for replication_task in await self.middleware.call("replication.query", [["transport", "!=", "LEGACY"],
                                                                                 ["enabled", "=", True]]):
            definition = {
                "direction": replication_task["direction"].lower(),
                "transport": await self._define_transport(
                    replication_task["transport"],
                    (replication_task["ssh_credentials"] or {}).get("id"),
                    replication_task["netcat_active_side"],
                    replication_task["netcat_active_side_port_min"],
                    replication_task["netcat_active_side_port_max"],
                ),
                "source-dataset": replication_task["source_datasets"],
                "target-dataset": replication_task["target_dataset"],
                "recursive": replication_task["recursive"],
                "exclude": replication_task["exclude"],
                "periodic-snapshot-tasks": [f"task_{periodic_snapshot_task['id']}"
                                            for periodic_snapshot_task in replication_task["periodic_snapshot_tasks"]
                                            if periodic_snapshot_task["id"] not in legacy_periodic_snapshot_tasks_ids],
                "auto": replication_task["auto"],
                "only-matching-schedule": replication_task["only_matching_schedule"],
                "allow-from-scratch": replication_task["allow_from_scratch"],
                "hold-pending-snapshots": replication_task["hold_pending_snapshots"],
                "retention-policy": replication_task["retention_policy"].lower(),
                "dedup": replication_task["dedup"],
                "large-block": replication_task["large_block"],
                "embed": replication_task["embed"],
                "compressed": replication_task["compressed"],
                "retries": replication_task["retries"],
            }

            if replication_task["naming_schema"]:
                definition["naming-schema"] = replication_task["naming_schema"]
            if replication_task["also_include_naming_schema"]:
                definition["also-include-naming-schema"] = replication_task["also_include_naming_schema"]
            # Use snapshots created by legacy periodic snapshot tasks
            for periodic_snapshot_task in replication_task["periodic_snapshot_tasks"]:
                if periodic_snapshot_task["id"] in legacy_periodic_snapshot_tasks_ids:
                    definition.setdefault("also-include-naming-schema", [])
                    definition["also-include-naming-schema"].append(periodic_snapshot_task["naming_schema"])
            if replication_task["schedule"] is not None:
                definition["schedule"] = zettarepl_schedule(replication_task["schedule"])
            if replication_task["restrict_schedule"] is not None:
                definition["restrict-schedule"] = zettarepl_schedule(replication_task["restrict_schedule"])
            if replication_task["lifetime_value"] is not None and replication_task["lifetime_unit"] is not None:
                definition["lifetime"] = lifetime_iso8601(replication_task["lifetime_value"],
                                                          replication_task["lifetime_unit"])
            if replication_task["compression"] is not None:
                definition["compression"] = replication_task["compression"]
            if replication_task["speed_limit"] is not None:
                definition["speed-limit"] = replication_task["speed_limit"]

            replication_tasks[f"task_{replication_task['id']}"] = definition

        definition = {
            "timezone": timezone,
            "periodic-snapshot-tasks": periodic_snapshot_tasks,
            "replication-tasks": replication_tasks,
        }

        # Test if validates
        Definition.from_data(definition)

        return definition

    async def _get_zettarepl_shell(self, transport, ssh_credentials):
        transport_definition = await self._define_transport(transport, ssh_credentials)
        transport = create_transport(transport_definition)
        return transport.shell(transport)

    async def _define_transport(self, transport, ssh_credentials=None, netcat_active_side=None,
                                netcat_active_side_port_min=None, netcat_active_side_port_max=None):

        if transport in ["SSH", "SSH+NETCAT", "LEGACY"]:
            if ssh_credentials is None:
                raise CallError(f"You should pass SSH credentials for {transport} transport")

            ssh_credentials = await self.middleware.call("keychaincredential.get_of_type", ssh_credentials,
                                                         "SSH_CREDENTIALS")

            transport_definition = dict(type="ssh", **await self._define_ssh_transport(ssh_credentials))

            if transport == "SSH+NETCAT":
                transport_definition["netcat-active-side"] = netcat_active_side.lower()
                transport_definition["netcat-active-side-port-min"] = netcat_active_side_port_min
                transport_definition["netcat-active-side-port-max"] = netcat_active_side_port_max
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
                self.logger.debug("Observer queue got %r", message)

                if isinstance(message, PeriodicSnapshotTaskStart):
                    self.state[f"periodic_snapshot_{message.task_id}"] = {
                        "state": "RUNNING",
                        "datetime": datetime.utcnow(),
                    }
                if isinstance(message, PeriodicSnapshotTaskSuccess):
                    self.state[f"periodic_snapshot_{message.task_id}"] = {
                        "state": "FINISHED",
                        "datetime": datetime.utcnow(),
                    }
                if isinstance(message, PeriodicSnapshotTaskError):
                    self.state[f"periodic_snapshot_{message.task_id}"] = {
                        "state": "ERROR",
                        "datetime": datetime.utcnow(),
                        "error": message.error,
                    }
                if isinstance(message, ReplicationTaskStart):
                    self.state[f"replication_{message.task_id}"] = {
                        "state": "RUNNING",
                        "datetime": datetime.utcnow(),
                    }
                if isinstance(message, ReplicationTaskSnapshotSuccess):
                    self.last_snapshot[f"replication_{message.task_id}"] = f"{message.dataset}@{message.snapshot}"
                if isinstance(message, ReplicationTaskSuccess):
                    self.state[f"replication_{message.task_id}"] = {
                        "state": "FINISHED",
                        "datetime": datetime.utcnow(),
                    }
                if isinstance(message, ReplicationTaskError):
                    self.state[f"replication_{message.task_id}"] = {
                        "state": "ERROR",
                        "datetime": datetime.utcnow(),
                        "error": message.error,
                    }
            except Exception:
                self.logger.warning("Unhandled exceptiom in observer_queue_reader", exc_info=True)


async def setup(middleware):
    try:
        await middleware.call("zettarepl.start")
    except Exception:
        pass
