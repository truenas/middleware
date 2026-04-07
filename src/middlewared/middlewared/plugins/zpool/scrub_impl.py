import time
from typing import Any, Callable, Literal

import truenas_pylibzfs

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
    truenas_pylibzfs.libzfs_types.ScanFunction.SCRUB,
    truenas_pylibzfs.libzfs_types.ScanFunction.ERRORSCRUB,
]:
    """Resolve a scan type string to a ScanFunction enum.

    Only SCRUB and ERRORSCRUB are allowed:
      - SCRUB: full data integrity scan of the entire pool
      - ERRORSCRUB: targeted scan of only blocks with known errors

    RESILVER is excluded because it is initiated automatically by ZFS
    when a replacement or re-attached vdev is detected.

    Raises ZpoolScanInvalidTypeException if scan_type is not recognized."""
    func = getattr(truenas_pylibzfs.libzfs_types.ScanFunction, scan_type.upper(), None)
    if func not in (
        truenas_pylibzfs.libzfs_types.ScanFunction.SCRUB,
        truenas_pylibzfs.libzfs_types.ScanFunction.ERRORSCRUB,
    ):
        raise ZpoolScanInvalidTypeException(scan_type)
    return func


def _get_scan_action(
    func: truenas_pylibzfs.libzfs_types.ScanFunction, action: str
) -> tuple[truenas_pylibzfs.libzfs_types.ScanFunction, truenas_pylibzfs.libzfs_types.ScanScrubCmd]:
    """Resolve an action string to the (ScanFunction, ScanScrubCmd) pair for zpool.scan().

      - START: begin or resume the scan (func=<scan_type>, cmd=NORMAL)
      - PAUSE: pause an in-progress scan (func=<scan_type>, cmd=PAUSE)
      - CANCEL: cancel the scan entirely (func=NONE, cmd=NORMAL)

    Raises ZpoolScanInvalidActionException if action is not recognized."""
    match action.upper():
        case "START":
            return func, truenas_pylibzfs.libzfs_types.ScanScrubCmd.NORMAL
        case "PAUSE":
            return func, truenas_pylibzfs.libzfs_types.ScanScrubCmd.PAUSE
        case "CANCEL":
            return (
                truenas_pylibzfs.libzfs_types.ScanFunction.NONE,
                truenas_pylibzfs.libzfs_types.ScanScrubCmd.NORMAL,
            )
        case _:
            raise ZpoolScanInvalidActionException(action)


def do_scan_action(
    tls: Any, pool_name: str, scan_type: str, action: str,
    zpool: truenas_pylibzfs.libzfs_types.ZFSPool | None = None
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

    if zpool is None:
        zpool = tls.lzh.open_pool(name=pool_name)
    try:
        zpool.scan(func=scan_func, cmd=scan_cmd)
    except truenas_pylibzfs.ZFSException as e:
        match e.code:
            case truenas_pylibzfs.ZFSError.EZFS_SCRUBBING:
                raise ZpoolScrubAlreadyRunningException(pool_name) from None
            case truenas_pylibzfs.ZFSError.EZFS_SCRUB_PAUSED:
                raise ZpoolScrubPausedException(pool_name) from None
            case truenas_pylibzfs.ZFSError.EZFS_SCRUB_PAUSED_TO_CANCEL:
                raise ZpoolScrubPausedToCancelException(pool_name) from None
            case truenas_pylibzfs.ZFSError.EZFS_ERRORSCRUBBING:
                raise ZpoolErrorScrubAlreadyRunningException(pool_name) from None
            case truenas_pylibzfs.ZFSError.EZFS_ERRORSCRUB_PAUSED:
                raise ZpoolErrorScrubPausedException(pool_name) from None
            case truenas_pylibzfs.ZFSError.EZFS_RESILVERING:
                raise ZpoolResiliverInProgressException(pool_name) from None
        raise


def run_impl(
    tls, pool_name: str, scan_type: str, action: str,
    *, wait: bool = False, progress_callback: Callable[[float | None, str | None], None] | None = None
) -> None:
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
    health = zpool.get_properties(properties={truenas_pylibzfs.ZPOOLProperty.HEALTH}).health.value
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
