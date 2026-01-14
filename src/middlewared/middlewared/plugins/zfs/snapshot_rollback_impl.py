import dataclasses
from typing import Any

import truenas_pylibzfs

from .exceptions import ZFSPathNotFoundException, ZFSPathNotASnapshotException

__all__ = ("rollback_impl",)


@dataclasses.dataclass(slots=True, kw_only=True)
class CollectNewerSnapshotsState:
    target_txg: int
    snaps: list[str]


# FIXME: add `hdl` to `truenas_pylibzfs` stubs
def __collect_child_datasets_callback(child_hdl: Any, state: list[str]) -> bool:
    """Callback for collecting child dataset names."""
    state.append(child_hdl.name)
    child_hdl.iter_filesystems(callback=__collect_child_datasets_callback, state=state)
    return True


def _collect_child_datasets(ds_hdl: Any, datasets: list[str]) -> None:
    """Recursively collect all child dataset names."""
    ds_hdl.iter_filesystems(callback=__collect_child_datasets_callback, state=datasets)


def __collect_newer_snapshots_callback(snap_hdl: Any, state: CollectNewerSnapshotsState) -> bool:
    """Callback for collecting snapshots newer than target."""
    props = snap_hdl.get_properties(properties={truenas_pylibzfs.ZFSProperty.CREATETXG})
    snap_txg = int(props.createtxg.value)
    if snap_txg > state.target_txg:
        state.snaps.append(snap_hdl.name)
    return True


def _rollback_single(dataset: str, snap_name: str) -> str:
    """Execute rollback for a single dataset.

    Args:
        dataset: Dataset path (e.g., 'pool/dataset')
        snap_name: Snapshot name (e.g., 'snap1')

    Returns:
        Name of snapshot rolled back to

    Raises:
        FileExistsError: If more recent snapshots exist
        FileNotFoundError: If snapshot doesn't exist
    """
    return truenas_pylibzfs.lzc.rollback(
        resource_name=dataset,
        snapshot_name=snap_name,
    )


def rollback_impl(
    tls: Any,
    path: str,
    recursive: bool = False,
    recursive_clones: bool = False,
    force: bool = False,
    recursive_rollback: bool = False,
) -> None:
    """Rollback a ZFS dataset to a snapshot.

    WARNING: This is a destructive change. All data written since the
    target snapshot was taken will be discarded.

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        path: Snapshot path to rollback to (e.g., 'pool/dataset@snapshot').
        recursive: Destroy any snapshots and bookmarks more recent than the one specified.
        recursive_clones: Like recursive, but also destroy any clones.
        force: Force unmount of any clones.
        recursive_rollback: Do a complete recursive rollback of each child snapshot.

    Raises:
        ZFSPathNotFoundException: If the snapshot doesn't exist
        ZFSPathNotASnapshotException: If path is not a snapshot path
        ValueError: If rollback fails
    """

    # Parse snapshot path
    if "@" not in path:
        raise ZFSPathNotASnapshotException(path)

    dataset, snap_name = path.rsplit("@", 1)

    # Verify snapshot exists
    try:
        tls.lzh.open_resource(name=path)
    except truenas_pylibzfs.ZFSException as e:
        if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(path)
        raise

    # Collect datasets to rollback
    if recursive_rollback:
        try:
            ds_hdl = tls.lzh.open_resource(name=dataset)
        except truenas_pylibzfs.ZFSException as e:
            if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                raise ZFSPathNotFoundException(dataset)
            raise

        datasets = [dataset]
        _collect_child_datasets(ds_hdl, datasets)
    else:
        datasets = [dataset]

    # Rollback each dataset
    for ds in datasets:
        snap_path = f"{ds}@{snap_name}"

        # For recursive_rollback, verify each child snapshot exists
        if recursive_rollback and ds != dataset:
            try:
                tls.lzh.open_resource(name=snap_path)
            except truenas_pylibzfs.ZFSException as e:
                if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                    raise ZFSPathNotFoundException(snap_path)
                raise

        # If recursive, destroy more recent snapshots first
        if recursive or recursive_clones:
            _destroy_newer_snapshots(tls, ds, snap_name, recursive_clones, force)

        try:
            _rollback_single(ds, snap_name)
        except FileNotFoundError:
            raise ZFSPathNotFoundException(snap_path)
        except FileExistsError as e:
            raise ValueError(f"Cannot rollback: more recent snapshots exist. Use recursive=True to destroy them. {e}")
        except (ValueError, OSError, PermissionError, RuntimeError) as e:
            raise ValueError(f"Failed to rollback snapshot: {e}")


def _destroy_newer_snapshots(tls: Any, dataset: str, target_snap: str, destroy_clones: bool, force: bool) -> None:
    """Destroy snapshots newer than the target snapshot.

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        dataset: Dataset path
        target_snap: Target snapshot name to rollback to
        destroy_clones: Also destroy clones of newer snapshots
        force: Force unmount
    """
    # Get the target snapshot's createtxg
    target_path = f"{dataset}@{target_snap}"
    try:
        target_rsrc = tls.lzh.open_resource(name=target_path)
        target_props = target_rsrc.get_properties(properties={truenas_pylibzfs.ZFSProperty.CREATETXG})
        target_txg = int(target_props.createtxg.value)
    except truenas_pylibzfs.ZFSException:
        return  # Target doesn't exist, let rollback handle the error

    # Get all snapshots for this dataset
    try:
        ds_hdl = tls.lzh.open_resource(name=dataset)
    except truenas_pylibzfs.ZFSException:
        return

    # Collect snapshots newer than target
    state = CollectNewerSnapshotsState(target_txg=target_txg, snaps=[])
    ds_hdl.iter_snapshots(callback=__collect_newer_snapshots_callback, state=state)
    newer_snaps = state.snaps

    # Destroy newer snapshots (in reverse order - newest first)
    for snap_path in reversed(newer_snaps):
        try:
            if destroy_clones:
                # Check for clones and destroy them first
                snap_rsrc = tls.lzh.open_resource(name=snap_path)
                props = snap_rsrc.get_properties(properties={truenas_pylibzfs.ZFSProperty.CLONES})
                if props.clones.value:
                    for clone in props.clones.value.split(","):
                        if clone:
                            try:
                                clone_rsrc = tls.lzh.open_resource(name=clone)
                                if force:
                                    clone_rsrc.unmount(force=True)
                                clone_rsrc.destroy()
                            except truenas_pylibzfs.ZFSException:
                                pass

            truenas_pylibzfs.lzc.destroy_snapshots(
                snapshot_names=(snap_path,),
                defer_destroy=False,
            )
        except truenas_pylibzfs.ZFSException:
            pass  # Continue with other snapshots
