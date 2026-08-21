import dataclasses
from typing import Any

import truenas_pylibzfs

from .exceptions import (
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSRollbackBlockedException,
    ZFSRollbackBlocker,
    ZFSRollbackBlockerReason,
)
from .utils import open_resource

__all__ = ("rollback_impl",)

CLONE_BLOCKER_LIMIT = 5
"""How many descendants of a single clone are collected before giving up on listing the rest."""


@dataclasses.dataclass(slots=True, kw_only=True)
class CollectNewerSnapshotsState:
    target_txg: int
    snaps: list[str]


@dataclasses.dataclass(slots=True, kw_only=True)
class CollectFirstNamesState:
    names: list[str]
    limit: int


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


def __collect_first_names_callback(hdl: Any, state: CollectFirstNamesState) -> bool:
    """Callback for collecting resource names, stopping once ``limit`` names have been seen."""
    state.names.append(hdl.name)
    return len(state.names) < state.limit


def _clone_destroy_blockers(tls: Any, clone: str, limit: int = CLONE_BLOCKER_LIMIT) -> tuple[str, ...]:
    """Return the names of the descendants that stop ``clone`` from being destroyed.

    Clones are destroyed non-recursively, so child datasets and snapshots of
    ``clone`` have to be dealt with by the caller first. An empty tuple means
    the clone can be destroyed. At most ``limit`` names are collected, so a
    full result means there may be more.
    """
    try:
        clone_rsrc = open_resource(tls, clone)
    except ZFSPathNotFoundException:
        return ()

    state = CollectFirstNamesState(names=[], limit=limit)
    try:
        clone_rsrc.iter_filesystems(callback=__collect_first_names_callback, state=state)
        if len(state.names) < limit:
            clone_rsrc.iter_snapshots(callback=__collect_first_names_callback, state=state, fast=True)
    except truenas_pylibzfs.ZFSException as e:
        raise ValueError(f"Failed to enumerate the descendants of {clone!r}: {e}") from None

    return tuple(state.names)


def _collect_rollback_blockers(
    tls: Any,
    datasets: list[str],
    target_snap: str,
    destroy_clones: bool,
) -> list[ZFSRollbackBlocker]:
    """Return every reason the snapshots newer than ``target_snap`` cannot be destroyed.

    Every dataset is inspected and every blocker recorded, so the caller can
    refuse the whole rollback in one go and report all of it at once.

    This is best effort. ``get_holds()`` only reflects user holds
    (``ds_userrefs``), while the kernel also refuses to destroy a snapshot that
    is long held - by an in-flight send or a ``.zfs/snapshot`` automount, for
    instance - which nothing here can observe.
    """
    blockers: list[ZFSRollbackBlocker] = []
    for dataset in datasets:
        for snap_path in _collect_newer_snapshots(tls, dataset, target_snap):
            try:
                snap_rsrc = open_resource(tls, snap_path)
            except ZFSPathNotFoundException:
                # Pruned while we were looking at it, so it blocks nothing.
                continue

            try:
                holds = snap_rsrc.get_holds()
                clones = snap_rsrc.get_clones()
            except truenas_pylibzfs.ZFSException as e:
                raise ValueError(f"Failed to inspect snapshot {snap_path!r}: {e}") from None

            if holds:
                blockers.append(ZFSRollbackBlocker(
                    snapshot=snap_path,
                    reason=ZFSRollbackBlockerReason.HOLDS,
                    names=tuple(holds),
                ))

            if not clones:
                continue

            if not destroy_clones:
                blockers.append(ZFSRollbackBlocker(
                    snapshot=snap_path,
                    reason=ZFSRollbackBlockerReason.CLONES,
                    names=tuple(clones),
                ))
                continue

            for clone in clones:
                if names := _clone_destroy_blockers(tls, clone):
                    blockers.append(ZFSRollbackBlocker(
                        snapshot=snap_path,
                        reason=ZFSRollbackBlockerReason.UNDESTROYABLE_CLONE,
                        names=names,
                        clone=clone,
                        truncated=len(names) >= CLONE_BLOCKER_LIMIT,
                    ))

    return blockers


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
        ZFSRollbackBlockedException: If a snapshot that has to be destroyed first cannot be destroyed
        ValueError: If rollback fails
    """

    # Parse snapshot path
    if "@" not in path:
        raise ZFSPathNotASnapshotException(path)

    dataset, snap_name = path.rsplit("@", 1)

    # Verify snapshot exists
    open_resource(tls, path)

    # Collect datasets to rollback
    if recursive_rollback:
        ds_hdl = open_resource(tls, dataset)
        datasets = [dataset]
        _collect_child_datasets(ds_hdl, datasets)

        # Verify each child snapshot exists before anything is destroyed or rolled back
        for ds in datasets[1:]:
            open_resource(tls, f"{ds}@{snap_name}")
    else:
        datasets = [dataset]

    if recursive or recursive_clones:
        # Refuse before destroying or rolling back anything.
        if blockers := _collect_rollback_blockers(tls, datasets, snap_name, recursive_clones):
            raise ZFSRollbackBlockedException(path, blockers)

    # Rollback each dataset
    for ds in datasets:
        snap_path = f"{ds}@{snap_name}"

        # If recursive, destroy more recent snapshots first
        if recursive or recursive_clones:
            _destroy_newer_snapshots(tls, ds, snap_name, recursive_clones, force)

        try:
            _rollback_single(ds, snap_name)
        except FileNotFoundError:
            raise ZFSPathNotFoundException(snap_path)
        except FileExistsError:
            try:
                conflicts = _collect_newer_snapshots(tls, ds, snap_name)
            except (ZFSPathNotFoundException, ValueError):
                conflicts = []
            raise ValueError(
                "Cannot rollback: more recent snapshots or bookmarks exist. Please pass `recursive: true` to "
                "delete the following snapshots and bookmarks recursively:\n" +
                "\n".join([f"  {snapshot}" for snapshot in conflicts])
            )
        except (ValueError, OSError, PermissionError, RuntimeError) as e:
            raise ValueError(f"Failed to rollback snapshot: {e}")


def _collect_newer_snapshots(tls: Any, dataset: str, target_snap: str) -> list[str]:
    """Return the snapshots of ``dataset`` that are newer than ``target_snap``.

    The names are ordered by ascending creation transaction group, matching the
    order ``zfs rollback -r`` reports the snapshots it would force-delete.
    """
    target_path = f"{dataset}@{target_snap}"
    target_rsrc = open_resource(tls, target_path)
    target_txg = int(target_rsrc.createtxg)
    ds_hdl = open_resource(tls, dataset)

    state = CollectNewerSnapshotsState(target_txg=target_txg, snaps=[])
    try:
        ds_hdl.iter_snapshots(
            callback=__collect_newer_snapshots_callback,
            state=state,
            min_transaction_group=target_txg,
            order_by_transaction_group=True,
        )
    except truenas_pylibzfs.ZFSException as e:
        raise ValueError(f"Failed to enumerate snapshots of {dataset!r}: {e}") from None
    return state.snaps


def _destroy_newer_snapshots(tls: Any, dataset: str, target_snap: str, destroy_clones: bool, force: bool) -> None:
    """Destroy snapshots newer than the target snapshot.

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        dataset: Dataset path
        target_snap: Target snapshot name to rollback to
        destroy_clones: Also destroy clones of newer snapshots
        force: Force unmount
    """
    # Collect snapshots newer than target (ordered oldest-first)
    newer_snaps = _collect_newer_snapshots(tls, dataset, target_snap)

    # Destroy newer snapshots (in reverse order - newest first)
    for snap_path in reversed(newer_snaps):
        if destroy_clones:
            try:
                snap_rsrc = open_resource(tls, snap_path)
            except ZFSPathNotFoundException:
                # Pruned since it was collected, so there is nothing left to destroy.
                continue

            try:
                clones = snap_rsrc.get_clones()
            except truenas_pylibzfs.ZFSException as e:
                raise ValueError(f"Failed to inspect snapshot {snap_path!r}: {e}") from None

            # Destroy any clones of this snapshot first. get_clones()
            # returns an empty tuple when there are none.
            for clone in clones:
                _destroy_clone(tls, clone, force)

        try:
            truenas_pylibzfs.lzc.destroy_snapshots(
                snapshot_names=(snap_path,),
                defer_destroy=False,
            )
        except (truenas_pylibzfs.ZFSException, truenas_pylibzfs.lzc.ZFSCoreException) as e:
            raise ValueError(f"Failed to destroy snapshot {snap_path!r} prior to rollback: {e}") from None


def _destroy_clone(tls: Any, clone: str, force: bool) -> None:
    """Destroy ``clone`` so that the snapshot it originates from can be destroyed.

    The clone is always unmounted first because destroying a resource does not
    unmount it, and a mounted filesystem is held by the kernel and so cannot be
    destroyed. ``force`` therefore controls how forcefully the unmount is
    attempted, not whether it is attempted at all. The encryption key is left
    loaded, matching what the ``zfs rollback`` CLI does when it unmounts a
    dependent clone.
    """
    try:
        clone_rsrc = open_resource(tls, clone)
    except ZFSPathNotFoundException:
        return

    if clone_rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        try:
            clone_rsrc.unmount(force=force, unload_encryption_key=False)
        except truenas_pylibzfs.ZFSException:
            # A failed unmount is deliberately not reported: the destroy below
            # fails too, with the reason the unmount was needed in the first place.
            pass

    try:
        tls.lzh.destroy_resource(name=clone)
    except truenas_pylibzfs.ZFSException as e:
        if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            # Destroyed by something else, which is all this call wanted.
            return
        raise ValueError(f"Failed to destroy clone {clone!r} prior to rollback: {e}") from None
