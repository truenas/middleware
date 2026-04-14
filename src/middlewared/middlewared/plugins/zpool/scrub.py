from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import ZpoolScrubRun, ZpoolScrubRunArgs, ZpoolScrubRunResult
from middlewared.service import Service, job
from middlewared.service.decorators import pass_thread_local_storage
from .scrub_impl import run_impl
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
        """Start, pause, or cancel a scrub on a ZFS pool.

        When ``action`` is START, the pool is validated before the scrub begins:
        the pool must be ONLINE or DEGRADED, must not have an active resilver,
        and the most recent scrub must be older than ``threshold`` days. If any
        of these checks fail the call returns silently (no error, no alert).

        PAUSE and CANCEL skip validation entirely and operate on the pool
        directly.

        At most 10 scrubs may run concurrently across all pools. Attempting to
        start an 11th raises an error.

        On a successful START a ``ScrubStarted`` alert is created. If the start
        fails for a reason other than the threshold or HA checks, a
        ``ScrubNotStarted`` alert is created instead.

        .. version-added:: 26.0.0
        """
        run_impl(self.context, tls.lzh, data, job.set_progress)
