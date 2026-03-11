from typing import Any

import truenas_pylibzfs

from .exceptions import (
    ZpoolErrorScrubAlreadyRunningException,
    ZpoolErrorScrubPausedException,
    ZpoolResiliverInProgressException,
    ZpoolScanInvalidAction,
    ZpoolScanInvalidType,
    ZpoolScrubAlreadyRunningException,
    ZpoolScrubPausedException,
    ZpoolScrubPausedToCancelException,
)

__all__ = ("do_scan_action",)


def _get_scan_function(scan_type: str) -> truenas_pylibzfs.enums.ScanFunction:
    """Resolve a scan type string to a ScanFunction enum.

    Only SCRUB and ERRORSCRUB are allowed:
      - SCRUB: full data integrity scan of the entire pool
      - ERRORSCRUB: targeted scan of only blocks with known errors

    RESILVER is excluded because it is initiated automatically by ZFS
    when a replacement or re-attached vdev is detected.

    Raises ZpoolScanInvalidType if scan_type is not recognized."""
    func = getattr(truenas_pylibzfs.enums.ScanFunction, scan_type.upper(), None)
    if func not in (
        truenas_pylibzfs.enums.ScanFunction.SCRUB,
        truenas_pylibzfs.enums.ScanFunction.ERRORSCRUB,
    ):
        raise ZpoolScanInvalidType(scan_type)
    return func


def _get_scan_action(
    func: truenas_pylibzfs.enums.ScanFunction, action: str
) -> tuple[truenas_pylibzfs.enums.ScanFunction, truenas_pylibzfs.enums.ScanScrubCmd]:
    """Resolve an action string to the (ScanFunction, ScanScrubCmd) pair for zpool.scan().

      - START: begin or resume the scan (func=<scan_type>, cmd=NORMAL)
      - PAUSE: pause an in-progress scan (func=<scan_type>, cmd=PAUSE)
      - CANCEL: cancel the scan entirely (func=NONE, cmd=NORMAL)

    Raises ZpoolScanInvalidAction if action is not recognized."""
    match action.upper():
        case "START":
            return func, truenas_pylibzfs.enums.ScanScrubCmd.NORMAL
        case "PAUSE":
            return func, truenas_pylibzfs.enums.ScanScrubCmd.PAUSE
        case "CANCEL":
            return (
                truenas_pylibzfs.enums.ScanFunction.NONE,
                truenas_pylibzfs.enums.ScanScrubCmd.NORMAL,
            )
        case _:
            raise ZpoolScanInvalidAction(action)


def do_scan_action(tls: Any, pool_name: str, scan_type: str, action: str) -> None:
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

    zpool = tls.lzh.open_pool(name=pool_name)
    try:
        zpool.scan(func=scan_func, cmd=scan_cmd)
    except truenas_pylibzfs.ZFSException as e:
        if e.code == truenas_pylibzfs.ZFSError.EZFS_SCRUBBING:
            raise ZpoolScrubAlreadyRunningException(pool_name) from None
        if e.code == truenas_pylibzfs.ZFSError.EZFS_SCRUB_PAUSED:
            raise ZpoolScrubPausedException(pool_name) from None
        if e.code == truenas_pylibzfs.ZFSError.EZFS_SCRUB_PAUSED_TO_CANCEL:
            raise ZpoolScrubPausedToCancelException(pool_name) from None
        if e.code == truenas_pylibzfs.ZFSError.EZFS_ERRORSCRUBBING:
            raise ZpoolErrorScrubAlreadyRunningException(pool_name) from None
        if e.code == truenas_pylibzfs.ZFSError.EZFS_ERRORSCRUB_PAUSED:
            raise ZpoolErrorScrubPausedException(pool_name) from None
        if e.code == truenas_pylibzfs.ZFSError.EZFS_RESILVERING:
            raise ZpoolResiliverInProgressException(pool_name) from None
        raise
