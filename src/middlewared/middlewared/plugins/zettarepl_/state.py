from collections import defaultdict
import re

from truenas_api_client import json as ejson

from middlewared.service import Service
from middlewared.utils.service.task_state import TaskStateMixin

RE_PERIODIC_SNAPSHOT_TASK_ID = re.compile(r"periodic_snapshot_task_([0-9]+)$")
RE_REPLICATION_TASK_ID = re.compile(r"replication_task_([0-9]+)$")


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
        return set(self.state.keys()) | set(self.definition_errors.keys()) | set(self.hold_tasks.keys())

    def _get_state_context(self):
        return self.middleware.call_sync("zettarepl.get_task_state_context")

    def _get_task_state(self, task_id, context):
        if self.error:
            return self.error

        if task_id in self.definition_errors:
            return self.definition_errors[task_id]

        if task_id in self.hold_tasks:
            return self.hold_tasks[task_id]

        state = self.state.get(task_id, {}).copy()

        if RE_PERIODIC_SNAPSHOT_TASK_ID.match(task_id):
            state["last_snapshot"] = self.last_snapshot.get(task_id)

        if m := RE_REPLICATION_TASK_ID.match(task_id):
            state["job"] = self.middleware.call_sync("zettarepl.get_task_state_job", context, int(m.group(1)))
            state["last_snapshot"] = self.last_snapshot.get(task_id)

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

        task_ids = (
            {f"periodic_snapshot_{k}" for k in definition["periodic-snapshot-tasks"]} |
            {f"replication_{k}" for k in definition["replication-tasks"]} |
            set(hold_tasks.keys())
        )
        for task_id in list(self.state.keys()):
            if task_id not in task_ids:
                self.state.pop(task_id, None)
        for task_id in list(self.last_snapshot.keys()):
            if task_id not in task_ids:
                self.last_snapshot.pop(task_id, None)
        for task_id in list(self.serializable_state.keys()):
            if task_id not in task_ids:
                self.serializable_state.pop(task_id, None)

    def get_internal_task_state(self, task_id):
        return self.state[task_id]

    def set_state(self, task_id, state):
        self.state[task_id] = state

        if state["state"] in ("ERROR", "FINISHED"):
            self.serializable_state[task_id]["state"] = state
            self.middleware.call_sync("zettarepl.flush_state")

        self._notify_state_change(task_id)

    def set_last_snapshot(self, task_id, last_snapshot):
        self.last_snapshot[task_id] = last_snapshot

        self.serializable_state[task_id]["last_snapshot"] = last_snapshot
        self.middleware.call_sync("zettarepl.flush_state")

        self._notify_state_change(task_id)

    def _notify_state_change(self, task_id):
        state = self._get_task_state(task_id, self._get_state_context())
        self.middleware.call_hook_sync("zettarepl.state_change", id_=task_id, fields=state)

    async def load_state(self):
        for snapshot in await self.middleware.call("datastore.query", "storage.task"):
            state = ejson.loads(snapshot["task_state"])
            if "last_snapshot" in state:
                self.last_snapshot[f"periodic_snapshot_task_{snapshot['id']}"] = state["last_snapshot"]
            if "state" in state:
                self.state[f"periodic_snapshot_task_{snapshot['id']}"] = state["state"]

        for replication in await self.middleware.call("datastore.query", "storage.replication"):
            state = ejson.loads(replication["repl_state"])
            if "last_snapshot" in state:
                self.last_snapshot[f"replication_task_{replication['id']}"] = state["last_snapshot"]
            if "state" in state:
                self.state[f"replication_task_{replication['id']}"] = state["state"]

    async def flush_state(self):
        for task_id, state in self.serializable_state.items():
            if RE_PERIODIC_SNAPSHOT_TASK_ID.match(task_id):
                try:
                    await self.middleware.call("datastore.update", "storage.task", int(task_id.split("_")[-1]),
                                               {"task_state": ejson.dumps(state)})
                except RuntimeError:
                    pass
            elif RE_REPLICATION_TASK_ID.match(task_id):
                try:
                    await self.middleware.call("datastore.update", "storage.replication", int(task_id.split("_")[-1]),
                                               {"repl_state": ejson.dumps(state)})
                except RuntimeError:
                    pass
