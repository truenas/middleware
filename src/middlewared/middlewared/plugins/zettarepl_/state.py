from collections import defaultdict
from dataclasses import dataclass, field
import re

from truenas_api_client import json as ejson

from middlewared.plugins.datastore.write import NoRowsWereUpdatedException
from middlewared.service import Service
from middlewared.utils.service.task_state import TaskStateMixin


@dataclass
class TaskStateDatastore:
    """How one kind of zettarepl task spells its task id, and where `flush_state` persists its state."""

    datastore: str
    column: str
    task_id_prefix: str
    task_id_re: re.Pattern = field(init=False, compare=False, repr=False)

    def __post_init__(self):
        self.task_id_re = re.compile(f"{self.task_id_prefix}([0-9]+)$")

    def task_id(self, id_: int) -> str:
        return f"{self.task_id_prefix}{id_}"

    def task_id_number(self, task_id: str) -> int | None:
        """Return the database id `task_id` refers to, or `None` when it names another kind of task."""
        if m := self.task_id_re.match(task_id):
            return int(m.group(1))

        return None


PERIODIC_SNAPSHOT_TASK_STATE = TaskStateDatastore("storage.task", "task_state", "periodic_snapshot_task_")
REPLICATION_TASK_STATE = TaskStateDatastore("storage.replication", "repl_state", "replication_task_")
TASK_STATE_DATASTORES = (PERIODIC_SNAPSHOT_TASK_STATE, REPLICATION_TASK_STATE)


def find_task_state_datastore(task_id: str) -> tuple[TaskStateDatastore, int] | None:
    """Match `task_id` to the datastore that persists its state, and to the task's database id.

    One-time replication tasks are keyed by job id and have no row, so they match nothing.
    """
    for task_state_datastore in TASK_STATE_DATASTORES:
        if (id_ := task_state_datastore.task_id_number(task_id)) is not None:
            return task_state_datastore, id_

    return None


class ZettareplService(Service, TaskStateMixin):

    task_state_methods = ["replication.run"]

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.state = {}
        self.error = None
        self.definition_errors = {}
        self.hold_tasks = {}
        self.last_snapshot = {}
        self.serializable_state = defaultdict(dict)

    def get_state(self):
        if self.error:
            return {
                "error": self.error,
            }

        context = self._get_state_context()

        return {
            "tasks": {
                task_id: self._get_task_state(task_id, context)
                for task_id in self._known_tasks_ids()
            }
        }

    def get_state_internal(self, task_id):
        return self.state.get(task_id)

    def _known_tasks_ids(self):
        return (set(self.state.keys()) | set(self.definition_errors.keys()) |
                set(self.hold_tasks.keys()) | set(self.serializable_state.keys()))

    def _get_state_context(self):
        return self.middleware.call_sync("zettarepl.get_task_state_context")

    def _get_task_state(self, task_id, context):
        if self.error:
            return self.error

        if task_id in self.definition_errors:
            return self.definition_errors[task_id]

        if task_id in self.hold_tasks:
            return self.hold_tasks[task_id]

        persisted = self.serializable_state.get(task_id, {})

        # Prefer the runtime state of an active task, fall back to the persisted state of an inactive one
        state = self.state.get(task_id)
        if state is None:
            state = dict(persisted.get("state") or {"state": "PENDING"})
        else:
            state = state.copy()

        if match := find_task_state_datastore(task_id):
            task_state_datastore, id_ = match

            state["last_snapshot"] = self.last_snapshot.get(task_id, persisted.get("last_snapshot"))

            if task_state_datastore is REPLICATION_TASK_STATE:
                state["job"] = self.middleware.call_sync("zettarepl.get_task_state_job", context, id_)

        return state

    def set_error(self, error):
        old_error = self.error
        self.error = error
        if old_error != self.error:
            for task_id in self._known_tasks_ids():
                self._notify_state_change(task_id)

    def set_definition_errors(self, definition_errors):
        old_definition_errors = self.definition_errors
        self.definition_errors = definition_errors
        for task_id in set(old_definition_errors.keys()) | set(self.definition_errors.keys()):
            self._notify_state_change(task_id)

    def notify_definition(self, definition, hold_tasks):
        old_hold_tasks = self.hold_tasks
        self.hold_tasks = hold_tasks
        for task_id in set(old_hold_tasks.keys()) | set(self.hold_tasks.keys()):
            self._notify_state_change(task_id)

        # Active tasks (enabled tasks from definition)
        active_task_ids = (
            {f"periodic_snapshot_{k}" for k in definition["periodic-snapshot-tasks"]} |
            {f"replication_{k}" for k in definition["replication-tasks"]} |
            set(hold_tasks.keys())
        )

        # Clear runtime state for tasks that are no longer active (but may still exist in DB as disabled)
        for task_id in list(self.state.keys()):
            if task_id not in active_task_ids:
                self.state.pop(task_id, None)

        # Clear last_snapshot from memory for tasks that are no longer active
        for task_id in list(self.last_snapshot.keys()):
            if task_id not in active_task_ids:
                self.last_snapshot.pop(task_id, None)

        # DO NOT clear serializable_state here - it should persist for disabled tasks
        # serializable_state will be cleared when tasks are explicitly deleted via remove_task()

    def get_internal_task_state(self, task_id):
        return self.state[task_id]

    def set_state(self, task_id, state):
        self.state[task_id] = state

        if state["state"] in ("ERROR", "FINISHED"):
            if task_id not in self.serializable_state:
                self.serializable_state[task_id] = {}
            self.serializable_state[task_id]["state"] = state
            self.middleware.call_sync("zettarepl.flush_state")

        self._notify_state_change(task_id)

    def set_last_snapshot(self, task_id, last_snapshot):
        self.last_snapshot[task_id] = last_snapshot

        if task_id not in self.serializable_state:
            self.serializable_state[task_id] = {}
        self.serializable_state[task_id]["last_snapshot"] = last_snapshot
        self.middleware.call_sync("zettarepl.flush_state")

        self._notify_state_change(task_id)

    def remove_task(self, task_id):
        """
        Remove all state for a task that has been deleted.
        This should be called when a task is deleted from the database.
        """
        self.state.pop(task_id, None)
        self.last_snapshot.pop(task_id, None)
        self.serializable_state.pop(task_id, None)
        self.definition_errors.pop(task_id, None)
        self.hold_tasks.pop(task_id, None)

    def _notify_state_change(self, task_id):
        state = self._get_task_state(task_id, self._get_state_context())
        self.middleware.call_hook_sync("zettarepl.state_change", id_=task_id, fields=state)

    async def _persisted_states(self):
        """Read every task state `flush_state` wrote to the database, keyed by task id."""
        states = {}
        for task_state_datastore in TASK_STATE_DATASTORES:
            for row in await self.middleware.call("datastore.query", task_state_datastore.datastore, [], {
                "select": ["id", task_state_datastore.column],
                "relationships": False,
            }):
                states[task_state_datastore.task_id(row["id"])] = ejson.loads(row[task_state_datastore.column])

        return states

    async def load_state(self):
        """Replace the in-memory task state with the state persisted in the database.

        Called on middlewared startup and on HA failover, so it must be safe to run against a state that is
        already populated. It drops tasks that no longer have a row, otherwise a recycled task id would report
        the deleted task's state.
        """
        persisted = await self._persisted_states()

        for task_id, state in persisted.items():
            # Load into serializable_state to preserve state for disabled tasks
            if state:
                self.serializable_state[task_id] = state
            if "last_snapshot" in state:
                self.last_snapshot[task_id] = state["last_snapshot"]
            if "state" in state:
                self.state[task_id] = state["state"]

        for task_id in self._known_tasks_ids() - set(persisted):
            if find_task_state_datastore(task_id):
                self.remove_task(task_id)

    async def flush_state(self):
        # Prevent `RuntimeError: dictionary changed size during iteration` when `serializable_state` is mutated
        # from other threads
        for task_id, state in list(self.serializable_state.items()):
            match = find_task_state_datastore(task_id)
            if match is None:
                continue

            task_state_datastore, id_ = match
            try:
                await self.middleware.call(
                    "datastore.update",
                    task_state_datastore.datastore,
                    id_,
                    {task_state_datastore.column: ejson.dumps(state)}
                )
            except NoRowsWereUpdatedException:
                pass
