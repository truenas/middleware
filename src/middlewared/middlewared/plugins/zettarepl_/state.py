from collections import defaultdict

from middlewared.client import ejson
from middlewared.service import periodic, Service


class ZettareplService(Service):

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
        jobs = {}
        for j in self.middleware.call_sync("core.get_jobs", [("method", "=", "replication.run")], {"order_by": ["id"]}):
            try:
                task_id = int(j["arguments"][0])
            except (IndexError, ValueError):
                continue

            jobs[f"replication_task_{task_id}"] = j

        return {"jobs": jobs}

    def _get_task_state(self, task_id, context):
        if self.error:
            return self.error

        if task_id in self.definition_errors:
            return self.definition_errors[task_id]

        if task_id in self.hold_tasks:
            return self.hold_tasks[task_id]

        state = self.state.get(task_id, {}).copy()

        if task_id.startswith("replication_task_"):
            state["job"] = context["jobs"].get(task_id)
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
            if f"replication_task_{task_id}" not in task_ids:
                self.serializable_state.pop(task_id, None)

    def get_internal_task_state(self, task_id):
        return self.state[task_id]

    def set_state(self, task_id, state):
        self.state[task_id] = state

        if task_id.startswith("replication_task_"):
            if state["state"] in ("ERROR", "FINISHED"):
                self.serializable_state[int(task_id.split("_")[-1])]["state"] = state

        self._notify_state_change(task_id)

    def set_last_snapshot(self, task_id, last_snapshot):
        self.last_snapshot[task_id] = last_snapshot

        if task_id.startswith("replication_task_"):
            self.serializable_state[int(task_id.split("_")[-1])]["last_snapshot"] = last_snapshot

        self._notify_state_change(task_id)

    def _notify_state_change(self, task_id):
        state = self._get_task_state(task_id, self._get_state_context())
        self.middleware.call_hook_sync("zettarepl.state_change", id=task_id, fields=state)

    async def load_state(self):
        for replication in await self.middleware.call("datastore.query", "storage.replication"):
            state = ejson.loads(replication["repl_state"])
            if "last_snapshot" in state:
                self.last_snapshot[f"replication_task_{replication['id']}"] = state["last_snapshot"]
            if "state" in state:
                self.state[f"replication_task_{replication['id']}"] = state["state"]

    @periodic(3600)
    async def flush_state(self):
        for task_id, state in self.serializable_state.items():
            try:
                await self.middleware.call("datastore.update", "storage.replication", task_id,
                                           {"repl_state": ejson.dumps(state)})
            except RuntimeError:
                pass
