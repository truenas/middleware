from __future__ import annotations

from typing import TYPE_CHECKING

import truenas_pylibzfs

from middlewared.api import api_method
from middlewared.api.current import (
    ZpoolScrubRunArgs,
    ZpoolScrubRunEntry,
    ZpoolScrubRunResult,
)
from middlewared.service import CallError, Service, job
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.service_exception import ValidationError

if TYPE_CHECKING:
    from middlewared.job import Job

from .exceptions import (
    ZpoolException,
    ZpoolNotFoundException,
    ZpoolScanInvalidActionException,
    ZpoolScanInvalidTypeException,
)
from .scrub_impl import run_impl, validate_pool


class ZpoolScrubService(Service):
    class Config:
        namespace = "zpool.scrub"
        cli_private = True

    @api_method(ZpoolScrubRunArgs, ZpoolScrubRunResult, roles=["POOL_WRITE"], check_annotations=True)
    @pass_thread_local_storage
    @job()
    def run(self, job: Job, tls, data: ZpoolScrubRunEntry) -> None:
        try:
            zpool, _ = validate_pool(tls.lzh, data.pool_name)
            run_impl(
                zpool, data.scan_type, data.action,
                wait=data.wait,
                progress_callback=job.set_progress,
            )
        except (ZpoolNotFoundException, ZpoolScanInvalidTypeException, ZpoolScanInvalidActionException) as e:
            raise ValidationError("zpool_scrub_run", e.message, e.errno) from e
        except ZpoolException as e:
            raise CallError(e.message, e.errno) from e
        except truenas_pylibzfs.ZFSException as e:
            raise CallError(str(e), e.code) from e
