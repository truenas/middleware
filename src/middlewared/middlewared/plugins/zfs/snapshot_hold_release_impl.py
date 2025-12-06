import dataclasses
from typing import TypedDict

from .exceptions import ZFSPathNotFoundException, ZFSPathNotASnapshotException

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None


__all__ = ("hold_impl", "HoldArgs", "release_impl", "ReleaseArgs")


class HoldArgs(TypedDict, total=False):
    path: str
    """Snapshot path to hold (e.g., 'pool/dataset@snapshot')."""
    tag: str
    """Hold tag name to apply."""
    recursive: bool
    """Apply hold recursively to matching snapshots in child datasets."""


class ReleaseArgs(TypedDict, total=False):
    path: str
    """Snapshot path to release holds from (e.g., 'pool/dataset@snapshot')."""
    tag: str | None
    """Specific tag to release. If None, releases all hold tags."""
    recursive: bool
    """Release holds recursively from matching snapshots in child datasets."""


@dataclasses.dataclass(slots=True, kw_only=True)
class CollectSnapshotsState:
    snapshots: list
    snap_name: str


def __collect_matching_snapshots_callback(ds_hdl, state: CollectSnapshotsState) -> bool:
    """Callback for collecting matching snapshot paths from child datasets."""
    snap_path = f"{ds_hdl.name}@{state.snap_name}"
    try:
        ds_hdl.root.open_resource(name=snap_path)
        state.snapshots.append(snap_path)
    except truenas_pylibzfs.ZFSException:
        # Snapshot doesn't exist for this child dataset, skip
        pass
    # Recurse into children
    ds_hdl.iter_filesystems(callback=__collect_matching_snapshots_callback, state=state)
    return True


def _collect_recursive_snapshots(tls, dataset: str, snap_name: str) -> list[str]:
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

    state = CollectSnapshotsState(snapshots=snapshots, snap_name=snap_name)
    ds_hdl.iter_filesystems(callback=__collect_matching_snapshots_callback, state=state)

    return state.snapshots


def hold_impl(tls, data: HoldArgs) -> None:
    """Create a hold on ZFS snapshot(s).

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        data: Hold parameters

    Raises:
        ZFSPathNotFoundException: If the snapshot doesn't exist
        ZFSPathNotASnapshotException: If path is not a snapshot path
        ZFSCoreException: If hold creation fails
    """
    path = data["path"]
    tag = data.get("tag", "truenas")
    recursive = data.get("recursive", False)

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


def release_impl(tls, data: ReleaseArgs) -> None:
    """Release hold(s) from ZFS snapshot(s).

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        data: Release parameters

    Raises:
        ZFSPathNotFoundException: If the snapshot doesn't exist
        ZFSPathNotASnapshotException: If path is not a snapshot path
        ZFSCoreException: If hold release fails
    """
    path = data["path"]
    tag = data.get("tag")  # None means release all holds
    recursive = data.get("recursive", False)

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
