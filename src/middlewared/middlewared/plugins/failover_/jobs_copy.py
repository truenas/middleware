import asyncio
import base64
import gzip
import os

from middlewared.service import CompoundService, Service
from middlewared.utils.service.task_state import TaskStateMixin


class JobsCopyService(Service):
    methods = set()

    class Config:
        private = True
        namespace = "failover.jobs_copy"

    async def register_method(self, method):
        self.methods.add(method)

    async def on_job_complete(self, job):
        if job["method"] not in self.methods:
            return

        if await self.middleware.call("failover.status") != "MASTER":
            return

        asyncio.ensure_future(self.send_job(job))

    async def send_job(self, job):
        try:
            logs = None
            if job["logs_path"] is not None:
                logs = await self.middleware.call("failover.jobs_copy.read_logs", job["logs_path"])
            await self.middleware.call("failover.call_remote", "failover.jobs_copy.receive_job", [job, logs])
        except Exception as e:
            self.logger.error("Error sending job %r %r: %r", job["method"], job["id"], e)

    async def receive_job(self, job, logs):
        if logs is not None:
            logs = await self.middleware.run_in_thread(lambda: gzip.decompress(base64.b64decode(logs.encode("ascii"))))

        await self.middleware.jobs.receive(job, logs)

    def read_logs(self, path):
        with open(path, "rb") as f:
            # We only want to send the last megabyte of the logs
            try:
                f.seek(-1000000, os.SEEK_END)
            except OSError:
                # The file is less than one megabyte, that is not an issue
                text = f.read()
            else:
                text = f.read()
                # Remove the leftovers of the first incomplete line
                text = text[text.find(b'\n') + 1:]

        return base64.b64encode(gzip.compress(text)).decode("ascii")


async def on_job_change(middleware, event_type, args):
    if event_type == "CHANGED" and args["fields"]["state"] in ["SUCCESS", "FAILED", "ABORTED"]:
        await middleware.call("failover.jobs_copy.on_job_complete", args["fields"])


async def setup(middleware):
    middleware.event_subscribe("core.get_jobs", on_job_change)

    for service in middleware._services.values():
        if isinstance(service, CompoundService):
            services = service.parts
        else:
            services = [service]

        for svc in services:
            if isinstance(svc, TaskStateMixin):
                for method in svc.task_state_methods:
                    await middleware.call("failover.jobs_copy.register_method", method)
