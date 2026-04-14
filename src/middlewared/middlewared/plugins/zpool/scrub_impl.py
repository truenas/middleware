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
    ZpoolTooManyScrubsException,
    ZpoolPoolUnhealthyException,
)
if TYPE_CHECKING:
    from middlewared.api.current import ZpoolScrubRun
    from middlewared.main import Middleware
    from middlewared.service import ServiceContext

__all__ = ("do_scan_action", "scrub_pool")

MAX_CONCURRENT_SCRUBS = 10

ScrubProgressCallback = Callable[[float | None, str | None], None]


def _count_running_scrubs(lzh: libzfs_types.ZFS) -> int:
    """Count the number of pools with an active scan."""
    count = [0]

    def _cb(pool, state):
        info = pool.scrub_info()
        if info is not None and info.state == libzfs_types.ScanState.SCANNING:
            state[0] += 1
        return True

    lzh.iter_pools(callback=_cb, state=count)
    return count[0]


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


def _open_pool_handle(lzh: libzfs_types.ZFS, pool_name: str) -> libzfs_types.ZFSPool:
    try:
        return lzh.open_pool(name=pool_name)
    except ZFSException as e:
        if e.code == ZFSError.EZFS_NOENT:
            raise ZpoolNotFoundException(pool_name) from e
        raise


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
    """Validate that a pool exists, is healthy, and is due for a scrub.

    Checks performed in order:
      1. On HA systems, this node must be the active controller.
      2. Non-boot pools must exist in the middleware datastore.
      3. Pool health must be ONLINE or DEGRADED.
      4. No resilver may be in progress.
      5. The last scrub (or pool create/import/scrub history entry) must
         be older than ``threshold`` days.

    Args:
        middleware: Middleware instance for service calls.
        lzh: Open libzfs handle.
        pool_name: Name of the zpool.
        threshold: Minimum age in days since the last scrub before a new
            one is considered due.

    Returns:
        The opened ZFSPool handle.

    Raises:
        ZpoolNotMasterNodeException: This node is not the active HA controller.
        ZpoolNotFoundException: Pool not in the datastore or ZFS.
        ZpoolPoolUnhealthyException: Pool is FAULTED, OFFLINE, etc.
        ZpoolResiliverInProgressException: A resilver is currently running.
        ZpoolScrubNotDueException: A recent scrub or pool event is within
            the threshold window.
    """
    if pool_name != middleware.call_sync('boot.pool_name'):
        if not middleware.call_sync('failover.is_single_master_node'):
            raise ZpoolNotMasterNodeException(pool_name)

        if not middleware.call_sync('datastore.query', 'storage.volume', [['vol_name', '=', pool_name]]):
            raise ZpoolNotFoundException(pool_name)

    # Open pool
    zpool = _open_pool_handle(lzh, pool_name)

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
            if any(zpool_cmd in cmd for zpool_cmd in ('zpool create', 'zpool import', 'zpool scrub')):
                middleware.logger.trace('Pool %r recent create/import within threshold window', pool_name)
                break
        else:
            start_scrub = True

    if not start_scrub:
        raise ZpoolScrubNotDueException(pool_name)

    return zpool


def scrub_pool(
    lzh: libzfs_types.ZFS, zpool: libzfs_types.ZFSPool,
    scan_type: Literal["SCRUB", "ERRORSCRUB"], action: Literal["START", "PAUSE", "CANCEL"],
    *, wait: bool = False, progress_callback: ScrubProgressCallback | None = None
) -> None:
    """Start, pause, or cancel a scan on a zpool.

    On START, enforces a system-wide limit of MAX_CONCURRENT_SCRUBS active
    scrubs. When ``wait`` is True and the action is START, polls
    ``zpool.scrub_info()`` until the scan finishes, is canceled, or is
    paused externally.

    Args:
        lzh: Open libzfs handle (used to count running scrubs).
        zpool: The pool to operate on.
        scan_type: "SCRUB" for a full integrity scan, "ERRORSCRUB" for a
            targeted scan of blocks with known errors.
        action: "START", "PAUSE", or "CANCEL".
        wait: If True and action is START, block until the scrub completes
            or is paused/canceled.
        progress_callback: Called during the wait loop with
            (percentage, description). May be None.

    Raises:
        ZpoolTooManyScrubsException: 10 or more scrubs already running.
        ZpoolScrubAlreadyRunningException: A scrub is already active on
            this pool.
        ZpoolScrubPausedToCancelException: A paused scrub must be canceled
            before starting an error scrub.
    """
    # Refuse to start if too many scrubs are already running
    if action.upper() == "START":
        running = _count_running_scrubs(lzh)
        if running >= MAX_CONCURRENT_SCRUBS:
            raise ZpoolTooManyScrubsException(running)

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
                if scrub.pass_scrub_pause:
                    if progress_callback:
                        progress_callback(100, f'{prog_scan_type} paused')
                    break
                if progress_callback and scrub.percentage is not None:
                    progress_callback(scrub.percentage, f'{prog_scan_type} in progress')

        time.sleep(1)


def run_impl(
    ctx: ServiceContext, lzh: libzfs_types.ZFS, data: ZpoolScrubRun,
    progress_cb: ScrubProgressCallback | None = None
) -> None:
    """Execute a scrub run request with alert management.

    For START: clears existing scrub alerts, validates the pool via
    validate_pool(), starts the scrub, and creates a ScrubStarted or
    ScrubNotStarted alert depending on the outcome. Threshold, HA, and
    resilver failures are swallowed silently (no error, no alert).

    For PAUSE/CANCEL: opens the pool directly and performs the action,
    skipping validation and alert management entirely.

    Args:
        ctx: Service context for middleware and alert calls.
        lzh: Open libzfs handle.
        data: Validated ZpoolScrubRun model with pool_name, scan_type,
            action, wait, and threshold.
        progress_cb: Optional progress callback forwarded to scrub_pool().
    """
    if data.action != "START":
        # PAUSE/CANCEL: skip threshold validation and alerts
        zpool = _open_pool_handle(lzh, data.pool_name)
        scrub_pool(lzh, zpool, data.scan_type, data.action)
        return

    for alert in ('ScrubNotStarted', 'ScrubStarted'):
        ctx.call_sync2(ctx.s.alert.oneshot_delete, alert, data.pool_name)

    try:
        pool = validate_pool(ctx.middleware, lzh, data.pool_name, data.threshold)
        scrub_pool(lzh, pool, data.scan_type, data.action, wait=data.wait, progress_callback=progress_cb)
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
