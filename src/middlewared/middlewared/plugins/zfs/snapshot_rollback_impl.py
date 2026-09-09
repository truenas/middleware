from collections.abc import Sequence
import dataclasses
import errno
import os
from typing import Any

import truenas_pylibzfs

from .destroy_impl import destroy_impl
from .exceptions import (
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSRollbackBlockedException,
    ZFSRollbackConflictException,
    ZFSRollbackFailedException,
)
from .utils import open_resource

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


def __collect_newer_snapshots_callback(snap_hdl: Any, state: CollectNewerSnapshotsState) -> bool:
    """Callback for collecting snapshots newer than target."""
    props = snap_hdl.get_properties(properties={truenas_pylibzfs.ZFSProperty.CREATETXG})
    if int(props.createtxg.value) > state.target_txg:
        state.snaps.append(snap_hdl.name)
    return True


def _collect_newer_snapshots(tls: Any, dataset: str, snap_name: str) -> list[str]:
    """Return the snapshots of ``dataset`` newer than ``snap_name``, oldest first.

    Raises:
        ZFSPathNotFoundException: ``dataset`` has no ``snap_name``.
    """
    target_txg = int(open_resource(tls, f"{dataset}@{snap_name}").createtxg)
    state = CollectNewerSnapshotsState(target_txg=target_txg, snaps=[])
    open_resource(tls, dataset).iter_snapshots(
        callback=__collect_newer_snapshots_callback,
        state=state,
        min_transaction_group=target_txg,
        order_by_transaction_group=True,
    )
    return state.snaps


def _collect_blockers(tls: Any, newer_snaps: Sequence[str], destroy_clones: bool) -> list[str]:
    """Describe each of ``newer_snaps`` that cannot be destroyed, and why."""
    blockers = []
    for snap_path in newer_snaps:
        try:
            snap_rsrc = open_resource(tls, snap_path)
        except ZFSPathNotFoundException:
            continue

        if holds := snap_rsrc.get_holds():
            blockers.append(f"{snap_path!r} has holds: {', '.join(holds)}. Release them before rolling back.")
        if (clones := snap_rsrc.get_clones()) and not destroy_clones:
            blockers.append(
                f"{snap_path!r} has dependent clones: {', '.join(clones)}. "
                "Pass `recursive_clones: true` to destroy them."
            )
    return blockers


def _destroy_clones_of(tls: Any, snap_path: str, force: bool) -> None:
    """Destroy the clones of ``snap_path``, descendants included, so that the snapshot itself can be destroyed.

    Matches ``zfs rollback -R``, which destroys a clone's own children and snapshots along with it.
    """
    try:
        clones = open_resource(tls, snap_path).get_clones()
    except ZFSPathNotFoundException:
        return

    for clone in clones:
        try:
            clone_rsrc = open_resource(tls, clone)
        except ZFSPathNotFoundException:
            continue

        if force and clone_rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
            # The recursive destroy unmounts the clone tree itself, but never forcibly.
            try:
                clone_rsrc.unmount(force=True, recursive=True, unload_encryption_key=False)
            except truenas_pylibzfs.ZFSException:
                pass  # The destroy below reports why the unmount was needed.

        failed, errnum = destroy_impl(tls, clone, recursive=True, all_snapshots=False, bypass=True, defer=False)
        if failed:
            raise ZFSRollbackFailedException(
                f"{failed}. It is a clone of {snap_path!r}, which has to be destroyed for the rollback.",
                errnum or errno.EFAULT,
            )


def _destroy_newer_snapshots(
    tls: Any, dataset: str, snap_name: str, newer_snaps: Sequence[str], destroy_clones: bool, force: bool
) -> None:
    """Destroy ``newer_snaps`` in one ioctl, so the kernel either destroys all of them or none."""
    if destroy_clones:
        for snap_path in newer_snaps:
            _destroy_clones_of(tls, snap_path, force)

    try:
        truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=newer_snaps, defer_destroy=False)
    except truenas_pylibzfs.lzc.ZFSCoreException as e:
        details = "; ".join(f"{name}: {os.strerror(err)}" for name, err in e.errors or ()) or str(e)
        raise ZFSRollbackFailedException(
            f"Failed to destroy the snapshots newer than {snap_name!r} on {dataset!r}: {details}", e.code
        ) from None


def _rollback(dataset: str, snap_name: str) -> None:
    """Roll ``dataset`` back to ``snap_name``."""
    try:
        truenas_pylibzfs.lzc.rollback(resource_name=dataset, snapshot_name=snap_name)
    except OSError as e:
        errnum = e.errno or errno.EFAULT
        message = f"Failed to rollback to {dataset}@{snap_name}: {os.strerror(errnum)}."
        if errnum == errno.EEXIST:
            message += (
                " Something newer than the snapshot still exists. Bookmarks are not destroyed by this "
                f"operation; remove one with `zfs destroy {dataset}#<bookmark>` and try again."
            )
        raise ZFSRollbackFailedException(message, errnum) from None


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
        recursive: Destroy any snapshots more recent than the one specified.
        recursive_clones: Like recursive, but also destroy any clones.
        force: Force unmount of any clones.
        recursive_rollback: Do a complete recursive rollback of each child snapshot.

    Raises:
        ZFSPathNotASnapshotException: If path is not a snapshot path
        ZFSPathNotFoundException: If the snapshot, or a child's snapshot, doesn't exist
        ZFSRollbackConflictException: If newer snapshots exist and no flag allows destroying them
        ZFSRollbackBlockedException: If a newer snapshot has holds, or clones that may not be destroyed
        ZFSRollbackFailedException: If a destroy or the rollback itself failed
        truenas_pylibzfs.ZFSException: If a resource could not be opened or walked
    """
    if "@" not in path:
        raise ZFSPathNotASnapshotException(path)

    dataset, snap_name = path.rsplit("@", 1)
    if not dataset or not snap_name or "@" in dataset:
        raise ZFSPathNotASnapshotException(path)

    datasets = [dataset]
    if recursive_rollback:
        open_resource(tls, dataset).iter_filesystems(callback=__collect_child_datasets_callback, state=datasets)

    # Enumerated for the whole tree before anything is touched: a blocker found lazily on a
    # child would only surface once the parent had already been rolled back.
    newer = [(ds, _collect_newer_snapshots(tls, ds, snap_name)) for ds in datasets]

    destroy_newer = recursive or recursive_clones
    if not destroy_newer:
        if conflicts := [snap for _, snaps in newer for snap in snaps]:
            raise ZFSRollbackConflictException(path, conflicts)
    elif blockers := [b for _, snaps in newer for b in _collect_blockers(tls, snaps, recursive_clones)]:
        raise ZFSRollbackBlockedException(path, blockers)

    for ds, newer_snaps in newer:
        if newer_snaps:
            _destroy_newer_snapshots(tls, ds, snap_name, newer_snaps, recursive_clones, force)
        _rollback(ds, snap_name)
