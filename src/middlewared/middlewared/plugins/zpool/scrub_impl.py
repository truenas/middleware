from __future__ import annotations
import time
from typing import Callable, Literal, TYPE_CHECKING

from truenas_pylibzfs import ZFSError, ZFSException, ZPOOLProperty, libzfs_types

from middlewared.plugins.zfs_.zfs_events import ScrubNotStartedAlert, ScrubStartedAlert
from .exceptions import (
    ZpoolErrorScrubAlreadyRunningException,
    ZpoolErrorScrubPausedException,
    ZpoolNotFoundException,
    ZpoolNotMasterNodeException,
    ZpoolScrubNotDueException,
    ZpoolResiliverInProgressException,
    ZpoolScanInvalidActionException,
    ZpoolScanInvalidTypeException,
    ZpoolScrubAlreadyRunningException,
    ZpoolScrubPausedException,
    ZpoolScrubPausedToCancelException,
    ZpoolPoolUnhealthyException,
)
if TYPE_CHECKING:
    from middlewared.api.current import ZpoolScrubRun
    from middlewared.main import Middleware
    from middlewared.service import ServiceContext

__all__ = ("do_scan_action", "scrub_pool")


ScrubProgressCallback = Callable[[float | None, str | None], None]


def _get_scan_function(scan_type: Literal["SCRUB", "ERRORSCRUB"]) -> Literal[
    libzfs_types.ScanFunction.SCRUB,
    libzfs_types.ScanFunction.ERRORSCRUB,
]:
    """Resolve a scan type string to a ScanFunction enum.

    Only SCRUB and ERRORSCRUB are allowed:
      - SCRUB: full data integrity scan of the entire pool
      - ERRORSCRUB: targeted scan of only blocks with known errors

    RESILVER is excluded because it is initiated automatically by ZFS
    when a replacement or re-attached vdev is detected.

    Raises ZpoolScanInvalidTypeException if scan_type is not recognized."""
    func = getattr(libzfs_types.ScanFunction, scan_type.upper(), None)
    if func not in (
        libzfs_types.ScanFunction.SCRUB,
        libzfs_types.ScanFunction.ERRORSCRUB,
    ):
        raise ZpoolScanInvalidTypeException(scan_type)
    return func


def _get_scan_action(
    func: libzfs_types.ScanFunction, action: Literal["START", "PAUSE", "CANCEL"]
) -> tuple[libzfs_types.ScanFunction, libzfs_types.ScanScrubCmd]:
    """Resolve an action string to the (ScanFunction, ScanScrubCmd) pair for zpool.scan().

      - START: begin or resume the scan (func=<scan_type>, cmd=NORMAL)
      - PAUSE: pause an in-progress scan (func=<scan_type>, cmd=PAUSE)
      - CANCEL: cancel the scan entirely (func=NONE, cmd=NORMAL)

    Raises ZpoolScanInvalidActionException if action is not recognized."""
    match action.upper():
        case "START":
            return func, libzfs_types.ScanScrubCmd.NORMAL
        case "PAUSE":
            return func, libzfs_types.ScanScrubCmd.PAUSE
        case "CANCEL":
            return (
                libzfs_types.ScanFunction.NONE,
                libzfs_types.ScanScrubCmd.NORMAL,
            )
        case _:
            raise ZpoolScanInvalidActionException(action)


def do_scan_action(
    zpool: libzfs_types.ZFSPool, scan_type: Literal["SCRUB", "ERRORSCRUB"], action: Literal["START", "PAUSE", "CANCEL"]
) -> None:
    """Start, pause, or cancel a scan on a zpool.

    scan_type: "SCRUB" for a full integrity scan, "ERRORSCRUB" for a targeted
        scan of blocks with known errors only.
    action: "START", "PAUSE", or "CANCEL".

    A SCRUB and ERRORSCRUB cannot run concurrently. Starting an ERRORSCRUB
    while a SCRUB is paused requires the paused SCRUB to be canceled first
    (raised as ZpoolScrubPausedToCancelException). Similarly, a SCRUB cannot
    be started while an ERRORSCRUB is running or paused.

    Raises pool-specific exceptions for conflict states (see exceptions.py).
    Unknown ZFSException errors are re-raised as-is."""
    func = _get_scan_function(scan_type)
    scan_func, scan_cmd = _get_scan_action(func, action)

    try:
        zpool.scan(func=scan_func, cmd=scan_cmd)
    except ZFSException as e:
        match e.code:
            case ZFSError.EZFS_SCRUBBING:
                raise ZpoolScrubAlreadyRunningException(zpool.name) from None
            case ZFSError.EZFS_SCRUB_PAUSED:
                raise ZpoolScrubPausedException(zpool.name) from None
            case ZFSError.EZFS_SCRUB_PAUSED_TO_CANCEL:
                raise ZpoolScrubPausedToCancelException(zpool.name) from None
            case ZFSError.EZFS_ERRORSCRUBBING:
                raise ZpoolErrorScrubAlreadyRunningException(zpool.name) from None
            case ZFSError.EZFS_ERRORSCRUB_PAUSED:
                raise ZpoolErrorScrubPausedException(zpool.name) from None
            case ZFSError.EZFS_RESILVERING:
                raise ZpoolResiliverInProgressException(zpool.name) from None
        raise


def validate_pool(
    middleware: Middleware, lzh: libzfs_types.ZFS, pool_name: str, threshold: int
) -> libzfs_types.ZFSPool:
    if pool_name != middleware.call_sync('boot.pool_name'):
        if not middleware.call_sync('failover.is_single_master_node'):
            raise ZpoolNotMasterNodeException(pool_name)

        if not middleware.call_sync('datastore.query', 'storage.volume', [['vol_name', '=', pool_name]]):
            raise ZpoolNotFoundException(pool_name)

    # Open pool
    try:
        zpool = lzh.open_pool(name=pool_name)
    except ZFSException as e:
        if e.code == ZFSError.EZFS_NOENT:
            raise ZpoolNotFoundException(pool_name) from e
        raise

    # Check pool health
    health = zpool.get_properties(properties={ZPOOLProperty.HEALTH}).health.value
    if health not in ("ONLINE", "DEGRADED"):
        raise ZpoolPoolUnhealthyException(pool_name, health)

    # Pre-check: reject if resilver is active
    scan = zpool.scrub_info()
    if (
        scan is not None
        and scan.func == libzfs_types.ScanFunction.RESILVER
        and scan.state == libzfs_types.ScanState.SCANNING
    ):
        raise ZpoolResiliverInProgressException(pool_name)

    # Threshold check via scan end_time
    start_scrub = False
    cutoff = int(time.time()) - (threshold - 1) * 86400

    if (
        scan
        and scan.func == libzfs_types.ScanFunction.SCRUB
        and scan.state == libzfs_types.ScanState.FINISHED
    ):
        if scan.end_time >= cutoff:
            middleware.logger.trace('Pool %r last scrub ended %r', pool_name, scan.end_time)
            raise ZpoolScrubNotDueException(pool_name)
        start_scrub = True

    # Slow path: check pool history for recent create/import
    if not start_scrub:
        for entry in zpool.iter_history(since=cutoff):
            cmd = entry.get('history command', '')
            if 'zpool create' in cmd or 'zpool import' in cmd:
                middleware.logger.trace('Pool %r recent create/import within threshold window', pool_name)
                break
        else:
            start_scrub = True

    if not start_scrub:
        raise ZpoolScrubNotDueException(pool_name)

    return zpool


def scrub_pool(
    zpool: libzfs_types.ZFSPool, scan_type: Literal["SCRUB", "ERRORSCRUB"], action: Literal["START", "PAUSE", "CANCEL"],
    *, wait: bool = False, progress_callback: ScrubProgressCallback | None = None
) -> None:
    """Start, pause, or cancel a scan on a zpool.

    Raises domain exceptions (Zpool*Exception) directly for internal
    callers to catch and handle as needed.
    """
    # Perform the scan action
    do_scan_action(zpool, scan_type, action)

    if not (wait and action.upper() == "START"):
        return

    if scan_type.upper() == 'ERRORSCRUB':
        prog_scan_type = 'Error scrub'
    else:
        prog_scan_type = 'Scrub'

    # Poll until scan completes (only meaningful for START)
    while True:
        scrub = zpool.scrub_info()
        if scrub is None:
            break

        match scrub.state:
            case libzfs_types.ScanState.FINISHED:
                if progress_callback:
                    progress_callback(100, f'{prog_scan_type} finished')
                break

            case libzfs_types.ScanState.CANCELED:
                break

            case libzfs_types.ScanState.SCANNING:
                if progress_callback and scrub.percentage is not None:
                    progress_callback(scrub.percentage, f'{prog_scan_type} in progress')

        time.sleep(1)


def run_impl(
    ctx: ServiceContext, lzh: libzfs_types.ZFS, data: ZpoolScrubRun,
    progress_cb: ScrubProgressCallback | None = None
) -> None:
    for alert in ('ScrubNotStarted', 'ScrubStarted'):
        ctx.call_sync2(ctx.s.alert.oneshot_delete, alert, data.pool_name)

    try:
        pool = validate_pool(ctx.middleware, lzh, data.pool_name, data.threshold)
        scrub_pool(pool, data.scan_type, data.action, wait=data.wait, progress_callback=progress_cb)
    except (ZpoolNotMasterNodeException, ZpoolScrubNotDueException, ZpoolResiliverInProgressException):
        # fail silently, no alert
        pass
    except Exception as e:
        ctx.call_sync2(
            ctx.s.alert.oneshot_create,
            ScrubNotStartedAlert(pool=data.pool_name, text=str(e)),
        )
    else:
        ctx.call_sync2(
            ctx.s.alert.oneshot_create,
            ScrubStartedAlert(data.pool_name),
        )
