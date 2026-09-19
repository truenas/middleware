from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import ZpoolScrubRun, ZpoolScrubRunArgs, ZpoolScrubRunResult
from middlewared.service import Service, job, private
from middlewared.service.decorators import pass_thread_local_storage

from .scrub_impl import run_impl

if TYPE_CHECKING:
    from middlewared.job import Job

__all__ = ("ZpoolScrubService",)


class ZpoolScrubService(Service):
    class Config:
        namespace = "zpool.scrub"
        cli_private = True

    @private
    @pass_thread_local_storage
    def run_impl(self, tls: Any, job: Job, data: ZpoolScrubRun) -> None:
        run_impl(self.context, tls.lzh, data, job.set_progress)

    @api_method(ZpoolScrubRunArgs, ZpoolScrubRunResult, roles=["POOL_WRITE"], check_annotations=True)
    @job()
    def run(self, job: Job, data: ZpoolScrubRun) -> None:
        """Start, pause, or cancel a scrub on a ZFS pool.

        When ``action`` is START, the pool is validated before the scrub begins:
        the pool must be ONLINE or DEGRADED, must not have an active resilver,
        and the most recent scrub must be older than ``threshold`` days. If any
        of these checks fail the call returns silently (no error, no alert).
        The job blocks until the scrub finishes, is paused, or is canceled.

        PAUSE and CANCEL skip validation entirely and operate on the pool
        directly.

        At most 10 scrubs may run concurrently across all pools. Attempting to
        start an 11th raises an error.

        On a successful START a ``ScrubStarted`` alert is created. If the start
        fails for a reason other than the threshold or HA checks, a
        ``ScrubNotStarted`` alert is created instead.

        .. versionadded:: 26.0.0
        """
        self.call_sync2(self.s.zpool.scrub.run_impl, job, data)
