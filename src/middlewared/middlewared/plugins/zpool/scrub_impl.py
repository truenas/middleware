import time
from typing import Callable, Literal

from truenas_pylibzfs import ZFSError, ZFSException, ZPOOLProperty, libzfs_types

from .exceptions import (
    ZpoolErrorScrubAlreadyRunningException,
    ZpoolErrorScrubPausedException,
    ZpoolNotFoundException,
    ZpoolResiliverInProgressException,
    ZpoolScanInvalidActionException,
    ZpoolScanInvalidTypeException,
    ZpoolScrubAlreadyRunningException,
    ZpoolScrubPausedException,
    ZpoolScrubPausedToCancelException,
    ZpoolPoolUnhealthyException,
)

__all__ = ("do_scan_action", "run_impl")


def _get_scan_function(scan_type: str) -> Literal[
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
    func: libzfs_types.ScanFunction, action: str
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


def do_scan_action(zpool: libzfs_types.ZFSPool, scan_type: str, action: str) -> None:
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
    lzh: libzfs_types.ZFS, pool_name: str
) -> tuple[libzfs_types.ZFSPool, libzfs_types.struct_zpool_scrub | None]:
    # Open pool
    try:
        zpool = lzh.open_pool(name=pool_name)
    except ZFSException as e:
        if e.code == ZFSError.EZFS_NOENT:
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
        and scrub.func == libzfs_types.ScanFunction.RESILVER
        and scrub.state == libzfs_types.ScanState.SCANNING
    ):
        raise ZpoolResiliverInProgressException(pool_name)  # don't raise alert

    return zpool, scrub


def run_impl(
    zpool: libzfs_types.ZFSPool, scan_type: str, action: str,
    *, wait: bool = False, progress_callback: Callable[[float | None, str | None], None] | None = None
) -> None:
    """Start, pause, or cancel a scan on a zpool.

    Raises domain exceptions (Zpool*Exception) directly for internal
    callers to catch and handle as needed.
    """
    # Perform the scan action
    do_scan_action(zpool, scan_type, action)

    if not (wait and action.upper() == "START"):
        return

    # Poll until scan completes (only meaningful for START)
    while True:
        time.sleep(5)
        scrub = zpool.scrub_info()
        if scrub is None:
            break

        match scrub.state:
            case libzfs_types.ScanState.FINISHED:
                if progress_callback:
                    progress_callback(100, f'{scan_type} finished')
                break

            case libzfs_types.ScanState.CANCELED:
                break

            case libzfs_types.ScanState.SCANNING:
                if progress_callback and scrub.percentage is not None:
                    progress_callback(scrub.percentage, f'{scan_type} in progress')
