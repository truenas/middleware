from middlewared.service import private


class TaskStateMixin:
    task_state_methods = NotImplemented

    @private
    async def get_task_state_context(self):
        jobs = {}
        for j in await self.middleware.call(
            "core.get_jobs",
            [("OR", [("method", "=", method) for method in self.task_state_methods])],
            {"order_by": ["id"]}
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
    async def get_task_state_job(self, context, task_id):
        return context["jobs"].get(task_id)

    @private
    async def persist_task_state_on_job_complete(self):
        async def on_job_change(middleware, event_type, args):
            if event_type == "CHANGED" and args["fields"]["state"] in ["SUCCESS", "FAILED", "ABORTED"]:
                job = args["fields"]

                if job["method"] in self.task_state_methods:
                    await self.middleware.call(
                        "datastore.update",
                        self._config.datastore,
                        job["arguments"][0],
                        {"job": dict(job, id=None, logs_path=None)},
                        {"prefix": self._config.datastore_prefix},
                    )

        self.middleware.event_subscribe("core.get_jobs", on_job_change)
