from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Iterable

from middlewared.plugins.datastore.write import NoRowsWereUpdatedException
from middlewared.service import private

if TYPE_CHECKING:
    from middlewared.main import Middleware


class TaskStateMixin:
    middleware: Middleware

    task_state_methods: Iterable[str]

    @private
    async def get_task_state_context(self) -> dict[str, Any]:
        jobs: dict[int, dict[str, Any]] = {}
        for j in await self.middleware.call(
            "core.get_jobs",
            [("OR", [("method", "=", method) for method in self.task_state_methods])],
            {"order_by": ["id"]},
        ):
            try:
                task_id = int(j["arguments"][0])
            except (IndexError, TypeError, ValueError):
                continue

            if task_id in jobs and jobs[task_id]["state"] == "RUNNING":
                # Newer task with the same name waiting in the queue, discard it and show the running task
                continue

            jobs[task_id] = j

        return {
            "jobs": jobs,
        }

    @private
    async def get_task_state_job(self, context: dict[str, Any], task_id: int) -> Any:
        return context["jobs"].get(task_id)

    def _task_state_datastore(self) -> str:
        # Legacy services keep their datastore on Config; typesafe services (whose Config no longer
        # carries a datastore) override this to read it off their service part.
        return self._config.datastore  # type: ignore[attr-defined,no-any-return]

    def _task_state_datastore_prefix(self) -> str:
        return self._config.datastore_prefix  # type: ignore[attr-defined,no-any-return]

    @private
    async def persist_task_state_on_job_complete(self) -> None:
        async def on_job_change(middleware: Middleware, event_type: str, args: dict[str, Any]) -> None:
            if event_type == "CHANGED" and args["fields"]["state"] in ["SUCCESS", "FAILED", "ABORTED"]:
                job = args["fields"]

                if job["method"] in self.task_state_methods:
                    with contextlib.suppress(NoRowsWereUpdatedException):
                        await self.middleware.call(
                            "datastore.update",
                            self._task_state_datastore(),
                            job["arguments"][0],
                            {"job": dict(job, id=None, logs_path=None)},
                            {"prefix": self._task_state_datastore_prefix()},
                        )

        self.middleware.event_subscribe("core.get_jobs", on_job_change)
