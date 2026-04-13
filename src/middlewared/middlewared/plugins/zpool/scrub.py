from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import ZpoolScrubRun, ZpoolScrubRunArgs, ZpoolScrubRunResult
from middlewared.service import Service, job
from middlewared.service.decorators import pass_thread_local_storage
from .scrub_impl import run
if TYPE_CHECKING:
    from middlewared.job import Job


class ZpoolScrubService(Service):
    class Config:
        namespace = "zpool.scrub"
        cli_private = True

    @api_method(ZpoolScrubRunArgs, ZpoolScrubRunResult, roles=["POOL_WRITE"], check_annotations=True)
    @pass_thread_local_storage
    @job()
    def run(self, job: Job, tls, data: ZpoolScrubRun) -> None:
        run(self.context, tls.lzh, data, job.set_progress)
