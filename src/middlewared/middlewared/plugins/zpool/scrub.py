from __future__ import annotations

import time
from typing import TYPE_CHECKING

import truenas_pylibzfs
from truenas_pylibzfs import ZPOOLProperty

from middlewared.api import api_method
from middlewared.api.current import (
    ZpoolScrubRunArgs,
    ZpoolScrubRunEntry,
    ZpoolScrubRunResult,
)
from middlewared.service import CallError, Service, job, private
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.service_exception import ValidationError

if TYPE_CHECKING:
    from middlewared.job import Job

from .exceptions import (
    ZpoolException,
    ZpoolNotFoundException,
    ZpoolPoolUnhealthyException,
    ZpoolResiliverInProgressException,
    ZpoolScanInvalidAction,
    ZpoolScanInvalidType,
)
from .scrub_impl import do_scan_action


class ZpoolScrubService(Service):
    class Config:
        namespace = "zpool.scrub"
        cli_private = True

    @private
    def run_impl(self, tls, pool_name, scan_type, action, *, wait=False, progress_callback=None):
        """Start, pause, or cancel a scan on a zpool.

        Raises domain exceptions (Zpool*Exception) directly for internal
        callers to catch and handle as needed.
        """
        # Open pool
        try:
            zpool = tls.lzh.open_pool(name=pool_name)
        except truenas_pylibzfs.ZFSException as e:
            if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                raise ZpoolNotFoundException(pool_name) from None
            raise

        # Check pool health
        health = zpool.get_properties(properties={ZPOOLProperty.HEALTH}).health.value
        if health not in ("ONLINE", "DEGRADED"):
            raise ZpoolPoolUnhealthyException(pool_name, health)

        # Pre-check: reject if resilver is active
        scrub = zpool.scrub_info()
        if (
            scrub is not None
            and scrub.func == truenas_pylibzfs.libzfs_types.ScanFunction.RESILVER
            and scrub.state == truenas_pylibzfs.libzfs_types.ScanState.SCANNING
        ):
            raise ZpoolResiliverInProgressException(pool_name)

        # Perform the scan action
        do_scan_action(tls, pool_name, scan_type, action, zpool)

        # Poll until scan completes (only meaningful for START)
        if wait and action.upper() == "START":
            while True:
                time.sleep(5)
                scrub = zpool.scrub_info()
                if scrub is None:
                    break
                if scrub.state == truenas_pylibzfs.libzfs_types.ScanState.FINISHED:
                    if progress_callback:
                        progress_callback(100, f'{scan_type} finished')
                    break
                if scrub.state == truenas_pylibzfs.libzfs_types.ScanState.CANCELED:
                    break
                if scrub.state == truenas_pylibzfs.libzfs_types.ScanState.SCANNING:
                    if progress_callback and scrub.percentage is not None:
                        progress_callback(scrub.percentage, f'{scan_type} in progress')

    @api_method(ZpoolScrubRunArgs, ZpoolScrubRunResult, roles=["POOL_WRITE"], check_annotations=True)
    @pass_thread_local_storage
    @job()
    def run(self, job: Job, tls, data: ZpoolScrubRunEntry) -> None:
        schema = "zpool_scrub_run"
        try:
            self.run_impl(
                tls, data.pool_name, data.scan_type, data.action,
                wait=data.wait,
                progress_callback=job.set_progress,
            )
        except (ZpoolNotFoundException, ZpoolScanInvalidType, ZpoolScanInvalidAction) as e:
            raise ValidationError(schema, e.message, e.errno) from e
        except ZpoolException as e:
            raise CallError(e.message, e.errno) from e
        except truenas_pylibzfs.ZFSException as e:
            raise CallError(str(e), e.code) from e
