import dataclasses
from typing import Any

import truenas_pylibzfs

from .exceptions import ZFSPathNotFoundException, ZFSPathNotASnapshotException

__all__ = ("hold_impl", "release_impl",)


@dataclasses.dataclass(slots=True, kw_only=True)
class CollectSnapshotsState:
    snapshots: list[str]
    snap_name: str
    lzh: truenas_pylibzfs.ZFS


def __collect_matching_snapshots_callback(ds_hdl: Any, state: CollectSnapshotsState) -> bool:
    """Callback for collecting matching snapshot paths from child datasets."""
    snap_path = f"{ds_hdl.name}@{state.snap_name}"
    try:
        state.lzh.open_resource(name=snap_path)
        state.snapshots.append(snap_path)
    except truenas_pylibzfs.ZFSException:
        # Snapshot doesn't exist for this child dataset, skip
        pass
    # Recurse into children
    ds_hdl.iter_filesystems(callback=__collect_matching_snapshots_callback, state=state)
    return True


def _collect_recursive_snapshots(tls: Any, dataset: str, snap_name: str) -> list[str]:
    """Collect all matching snapshot paths recursively.

    For recursive operations, finds all snapshots with the same name
    in child datasets.

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        dataset: Parent dataset path
        snap_name: Snapshot name to match

    Returns:
        List of snapshot paths (e.g., ['pool/ds@snap', 'pool/ds/child@snap'])
    """
    snapshots = []

    # Check if parent snapshot exists and add it
    parent_snap = f"{dataset}@{snap_name}"
    try:
        tls.lzh.open_resource(name=parent_snap)
        snapshots.append(parent_snap)
    except truenas_pylibzfs.ZFSException as e:
        if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(parent_snap)
        raise

    # Collect from child datasets
    try:
        ds_hdl = tls.lzh.open_resource(name=dataset)
    except truenas_pylibzfs.ZFSException as e:
        if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(dataset)
        raise

    state = CollectSnapshotsState(snapshots=snapshots, snap_name=snap_name, lzh=tls.lzh)
    ds_hdl.iter_filesystems(callback=__collect_matching_snapshots_callback, state=state)

    return state.snapshots


def hold_impl(tls: Any, path: str, tag: str = "truenas", recursive: bool = False) -> None:
    """Create a hold on ZFS snapshot(s).

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        path: Snapshot path to hold (e.g., 'pool/dataset@snapshot').
        tag: Hold tag name to apply.
        recursive: Apply hold recursively to matching snapshots in child datasets.

    Raises:
        ZFSPathNotFoundException: If the snapshot doesn't exist
        ZFSPathNotASnapshotException: If path is not a snapshot path
        ZFSCoreException: If hold creation fails
    """

    # Parse snapshot path
    if "@" not in path:
        raise ZFSPathNotASnapshotException(path)

    dataset, snap_name = path.rsplit("@", 1)

    # Build list of snapshots to hold
    if recursive:
        snapshot_paths = _collect_recursive_snapshots(tls, dataset, snap_name)
    else:
        # Single snapshot - verify it exists
        try:
            tls.lzh.open_resource(name=path)
        except truenas_pylibzfs.ZFSException as e:
            if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                raise ZFSPathNotFoundException(path)
            raise
        snapshot_paths = [path]

    if not snapshot_paths:
        raise ZFSPathNotFoundException(path)

    # Build holds tuples: (snapshot_name, hold_key)
    holds = [(snap_path, tag) for snap_path in snapshot_paths]

    try:
        # Returns tuple of snapshots that no longer exist (not a failure)
        truenas_pylibzfs.lzc.create_holds(holds=holds)
    except truenas_pylibzfs.lzc.ZFSCoreException:
        raise


def release_impl(tls: Any, path: str, tag: str | None = None, recursive: bool = False) -> None:
    """Release hold(s) from ZFS snapshot(s).

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        path: Snapshot path to release holds from (e.g., 'pool/dataset@snapshot').
        tag: Specific tag to release. If None, releases all hold tags.
        recursive: Release holds recursively from matching snapshots in child datasets.

    Raises:
        ZFSPathNotFoundException: If the snapshot doesn't exist
        ZFSPathNotASnapshotException: If path is not a snapshot path
        ZFSCoreException: If hold release fails
    """

    # Parse snapshot path
    if "@" not in path:
        raise ZFSPathNotASnapshotException(path)

    dataset, snap_name = path.rsplit("@", 1)

    # Build list of snapshots to release holds from
    if recursive:
        snapshot_paths = _collect_recursive_snapshots(tls, dataset, snap_name)
    else:
        # Single snapshot - verify it exists
        try:
            tls.lzh.open_resource(name=path)
        except truenas_pylibzfs.ZFSException as e:
            if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                raise ZFSPathNotFoundException(path)
            raise
        snapshot_paths = [path]

    if not snapshot_paths:
        raise ZFSPathNotFoundException(path)

    # Build set of (snapshot_path, tag) tuples to release
    holds_to_release = set()
    for snap_path in snapshot_paths:
        if tag is not None:
            # Release specific tag
            holds_to_release.add((snap_path, tag))
        else:
            # Release all holds - need to get current holds first
            try:
                rsrc = tls.lzh.open_resource(name=snap_path)
                current_holds = rsrc.get_holds()
                for hold_tag in current_holds:
                    holds_to_release.add((snap_path, hold_tag))
            except truenas_pylibzfs.ZFSException:
                # Snapshot may have been deleted, skip
                pass

    if not holds_to_release:
        # No holds to release
        return

    try:
        # Returns tuple of holds that no longer exist (not a failure)
        truenas_pylibzfs.lzc.release_holds(holds=holds_to_release)
    except truenas_pylibzfs.lzc.ZFSCoreException:
        raise
