from collections.abc import Callable, Iterator, Sequence
import contextlib
import dataclasses
import errno
import logging
import os
from typing import Any

import truenas_pylibzfs

from .exceptions import (
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSRollbackBlockedException,
    ZFSRollbackBlocker,
    ZFSRollbackBlockerReason,
    ZFSRollbackConflictException,
    ZFSRollbackFailedException,
)
from .snapshot_rollback_helpers import (
    DestroyFailure,
    classify_destroy_failure,
    rollback_failure_message,
)
from .utils import open_resource

__all__ = ("rollback_impl",)

logger = logging.getLogger(__name__)

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
    newer: Sequence[tuple[str, list[str]]],
    destroy_clones: bool,
) -> list[ZFSRollbackBlocker]:
    """Return every reason the snapshots newer than the rollback target cannot be destroyed.

    ``newer`` pairs each affected dataset with the snapshot paths newer than the
    target. Every dataset is inspected and every blocker recorded, so the caller
    can refuse the whole rollback in one go and report all of it at once.

    This is best effort. ``get_holds()`` only reflects user holds
    (``ds_userrefs``), while the kernel also refuses to destroy a snapshot that
    is long held - by an in-flight send or a ``.zfs/snapshot`` automount, for
    instance - which nothing here can observe; the batched destroy reports those
    from the kernel's own error list instead.
    """
    blockers: list[ZFSRollbackBlocker] = []
    for _, newer_snaps in newer:
        for snap_path in newer_snaps:
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


@contextlib.contextmanager
def _tolerate_history_write_failure(action: str) -> Iterator[None]:
    """Run one committed ZFS operation, tolerating a failed ``zpool history`` write.

    ``truenas_pylibzfs`` logs to the pool history only after the operation has
    already succeeded, and raises a bare RuntimeError when that write fails. The
    operation is done at that point, so the failure is logged and swallowed.
    ZFSException and ZFSCoreException both derive from RuntimeError, so only the
    exact type is tolerated.
    """
    try:
        yield
    except RuntimeError as e:
        if type(e) is not RuntimeError:
            raise
        logger.warning("%s: succeeded, but the pool history entry could not be written", action, exc_info=True)


def _rollback_single(dataset: str, snap_name: str, completed: Sequence[str], destroyed_newer: bool) -> None:
    """Roll ``dataset`` back to its ``snap_name`` snapshot.

    ``destroyed_newer`` says whether the newer snapshots of ``dataset`` were
    destroyed to get this far, which is the part of a failure here that cannot
    be undone.

    Raises:
        ZFSRollbackFailedException: The kernel refused the rollback.
    """
    path = f"{dataset}@{snap_name}"
    try:
        with _tolerate_history_write_failure(f"rollback of {dataset!r} to {snap_name!r}"):
            truenas_pylibzfs.lzc.rollback(resource_name=dataset, snapshot_name=snap_name)
    except OSError as e:
        errnum = e.errno or errno.EFAULT
        message = rollback_failure_message(path=path, dataset=dataset, errnum=errnum)
        if destroyed_newer:
            message += (
                f" The snapshots newer than {snap_name!r} were already destroyed, so "
                f"{dataset!r} cannot be returned to its previous state."
            )
        raise ZFSRollbackFailedException(message, errnum, completed=completed) from None


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
        ZFSRollbackConflictException: If snapshots newer than the target exist and may
            not be destroyed
        ZFSRollbackBlockedException: If a snapshot that has to be destroyed first cannot be destroyed
        ZFSRollbackFailedException: If the rollback, or a destroy it depends on, failed
        ValueError: If the state the rollback depends on could not be established
    """

    # Parse snapshot path. Both components must be non-empty and the dataset half
    # must not itself contain '@', or the name is not a snapshot path at all.
    if "@" not in path:
        raise ZFSPathNotASnapshotException(path)

    dataset, snap_name = path.rsplit("@", 1)
    if not dataset or not snap_name or "@" in dataset:
        raise ZFSPathNotASnapshotException(path)

    # Collect datasets to rollback
    if recursive_rollback:
        ds_hdl = open_resource(tls, dataset)
        datasets = [dataset]
        _collect_child_datasets(ds_hdl, datasets)
    else:
        datasets = [dataset]

    # Enumerate before anything is destroyed or rolled back: every dataset has to have
    # the target snapshot, and every conflict has to be known, before the first dataset
    # is touched. Otherwise a blocker on a child is only found once the parent has
    # already been rolled back, leaving the tree half rolled back.
    newer = [(ds, _collect_newer_snapshot_paths(tls, ds, snap_name)) for ds in datasets]

    destroy_newer = recursive or recursive_clones
    if not destroy_newer:
        if conflicts := [snap for _, snaps in newer for snap in snaps]:
            raise ZFSRollbackConflictException(path, conflicts)
    elif blockers := _collect_rollback_blockers(tls, newer, recursive_clones):
        raise ZFSRollbackBlockedException(path, blockers)

    completed: list[str] = []
    for ds, newer_snaps in newer:
        destroyed_newer = destroy_newer and bool(newer_snaps)
        if destroy_newer:
            _destroy_newer_snapshots(tls, ds, newer_snaps, snap_name, recursive_clones, force, completed)

        reservation = _capture_volume_reservation(tls, ds)
        _rollback_single(ds, snap_name, completed, destroyed_newer)
        if reservation is not None:
            _restore_volume_reservation(tls, ds, reservation)

        completed.append(ds)


def _collect_newer_snapshots(ds_hdl: Any, target_txg: int) -> list[str]:
    """Return the snapshots of ``ds_hdl`` that are newer than ``target_txg``.

    The names are ordered by ascending creation transaction group, matching the
    order ``zfs rollback -r`` reports the snapshots it would force-delete.
    """
    state = CollectNewerSnapshotsState(target_txg=target_txg, snaps=[])
    try:
        ds_hdl.iter_snapshots(
            callback=__collect_newer_snapshots_callback,
            state=state,
            min_transaction_group=target_txg,
            order_by_transaction_group=True,
        )
    except truenas_pylibzfs.ZFSException as e:
        raise ValueError(f"Failed to enumerate snapshots of {ds_hdl.name!r}: {e}") from None
    return state.snaps


def _collect_newer_snapshot_paths(tls: Any, dataset: str, target_snap: str) -> list[str]:
    """Enumerate the snapshots newer than ``dataset@target_snap``, once.

    Raises:
        ZFSPathNotFoundException: ``dataset`` has no ``target_snap``, which is how a
            recursive rollback finds a child that cannot be rolled back before
            anything is destroyed.
    """
    target_rsrc = open_resource(tls, f"{dataset}@{target_snap}")
    target_txg = int(target_rsrc.createtxg)
    ds_hdl = open_resource(tls, dataset)
    return _collect_newer_snapshots(ds_hdl, target_txg)


def _destroy_newer_snapshots(
    tls: Any,
    dataset: str,
    snapshots: Sequence[str],
    target_snap: str,
    destroy_clones: bool,
    force: bool,
    completed: Sequence[str],
) -> None:
    """Destroy the snapshots newer than ``target_snap`` so ``dataset`` can be rolled back.

    Clones are destroyed one at a time first: a snapshot with a clone cannot be
    destroyed, and the clone has to be unmounted before it can go. The snapshots
    themselves then go in a single ioctl.
    """
    if destroy_clones:
        for snap_path in reversed(snapshots):
            _destroy_clones_of(tls, snap_path, force, completed)

    _destroy_batch(
        tls,
        objects=list(reversed(snapshots)),
        destroy=lambda names: truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=names, defer_destroy=False),
        dataset=dataset,
        target_snap=target_snap,
        clones_destroyed=destroy_clones,
        completed=completed,
    )


def _destroy_failure_prefix(dataset: str, target_snap: str) -> str:
    """Opening of the message reporting that the destroy the rollback depends on failed."""
    return f"Failed to destroy the snapshots newer than {target_snap!r} on {dataset!r} before rolling it back: "


def _destroy_batch(
    tls: Any,
    *,
    objects: Sequence[str],
    destroy: Callable[[Sequence[str]], None],
    dataset: str,
    target_snap: str,
    clones_destroyed: bool,
    completed: Sequence[str],
) -> None:
    """Destroy ``objects``, the snapshots newer than ``target_snap``, in one ioctl.

    The kernel checks every object before destroying any, so the ioctl either
    destroys the whole batch or destroys nothing, and the exception names the
    objects that stood in the way - including the long holds the pre-flight
    cannot see. Objects destroyed by something else in the meantime are silently
    ignored by the kernel.
    """
    if not objects:
        return

    try:
        with _tolerate_history_write_failure(f"destroy of the newer snapshots of {dataset!r}"):
            destroy(objects)
    except truenas_pylibzfs.lzc.ZFSCoreException as e:
        failure = classify_destroy_failure(
            submitted=set(objects),
            errors=e.errors,
            code=e.code,
            clones_destroyed=clones_destroyed,
        )
        _raise_destroy_failure(
            tls,
            failure,
            dataset=dataset,
            target_snap=target_snap,
            completed=completed,
        )
    except truenas_pylibzfs.ZFSException as e:
        raise ZFSRollbackFailedException(
            _destroy_failure_prefix(dataset, target_snap) + str(e),
            errno.EFAULT,
            completed=completed,
        ) from None


def _raise_destroy_failure(
    tls: Any,
    failure: DestroyFailure,
    *,
    dataset: str,
    target_snap: str,
    completed: Sequence[str],
) -> None:
    """Report a failed batched destroy, returning only when everything that failed had vanished."""
    prefix = _destroy_failure_prefix(dataset, target_snap)
    if failure.blockers:
        blockers = [_with_clone_names(tls, blocker) for blocker in failure.blockers]
        raise ZFSRollbackBlockedException(f"{dataset}@{target_snap}", blockers, completed=completed) from None
    elif failure.other:
        raise ZFSRollbackFailedException(
            prefix + "; ".join(f"{name}: {os.strerror(err)}" for name, err in failure.other),
            failure.other[0][1],
            completed=completed,
        ) from None
    elif failure.state_unknown:
        try:
            leftover = _collect_newer_snapshot_paths(tls, dataset, target_snap)
            still_there = "\n".join(f"  {name}" for name in leftover) or "  (none)"
        except (ZFSPathNotFoundException, ValueError, truenas_pylibzfs.ZFSException, RuntimeError):
            still_there = "  (could not be listed)"
        raise ZFSRollbackFailedException(
            prefix + f"{os.strerror(failure.code)}. The destroy was interrupted after it started, so an unknown "
            f"number of them are already gone and {dataset!r} was not rolled back. Snapshots still newer than "
            f"{target_snap!r}:\n{still_there}",
            failure.code,
            completed=completed,
        ) from None
    elif not failure.reported_per_object:
        raise ZFSRollbackFailedException(
            prefix + f"{os.strerror(failure.code)}.",
            failure.code,
            completed=completed,
        ) from None
    else:
        logger.warning("%s: the kernel reported these as already gone: %s", dataset, ", ".join(failure.vanished))


def _with_clone_names(tls: Any, blocker: ZFSRollbackBlocker) -> ZFSRollbackBlocker:
    """Name the clones of a kernel-reported clone blocker, which reports an errno and nothing else."""
    if blocker.reason not in (ZFSRollbackBlockerReason.CLONES, ZFSRollbackBlockerReason.CLONE_DESTROY_FAILED):
        return blocker

    try:
        clones = open_resource(tls, blocker.snapshot).get_clones()
    except (ZFSPathNotFoundException, truenas_pylibzfs.ZFSException):
        return blocker
    return dataclasses.replace(blocker, names=tuple(clones))


def _destroy_clones_of(tls: Any, snap_path: str, force: bool, completed: Sequence[str]) -> None:
    """Destroy the clones of ``snap_path`` so that the snapshot itself can be destroyed."""
    try:
        snap_rsrc = open_resource(tls, snap_path)
    except ZFSPathNotFoundException:
        # Pruned since it was collected, so there is nothing left to destroy.
        return

    try:
        clones = snap_rsrc.get_clones()
    except truenas_pylibzfs.ZFSException as e:
        raise ZFSRollbackFailedException(
            f"Failed to inspect snapshot {snap_path!r}: {e}",
            errno.EFAULT,
            completed=completed,
        ) from None

    # get_clones() returns an empty tuple when there are none.
    for clone in clones:
        _destroy_clone(tls, clone, force, completed)


def _destroy_clone(tls: Any, clone: str, force: bool, completed: Sequence[str]) -> None:
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
        # A clone that cannot be destroyed - typically because something is
        # holding it open - is an operational failure, not bad input, and in a
        # recursive rollback it can strike after earlier datasets already
        # rolled back, so the exception has to carry the completed list.
        raise ZFSRollbackFailedException(
            f"Failed to destroy clone {clone!r} prior to rollback: {e}",
            errno.EBUSY,
            completed=completed,
        ) from None


def _prop_int(prop: Any) -> int:
    """Read a numeric ZFS property, treating an unset property as zero."""
    if prop is None or prop.value is None:
        return 0
    return int(prop.value)


def _capture_volume_reservation(tls: Any, dataset: str) -> int | None:
    """Return the ``volsize`` of ``dataset`` when its ``refreservation`` has to be restored afterwards.

    A rollback can change the volsize of a volume, which leaves a thick
    provisioned volume with a ``refreservation`` that no longer covers it.
    ``None`` means there is nothing to restore: ``dataset`` is not a volume, it
    is thin provisioned, or it could not be inspected.
    """
    try:
        rsrc = open_resource(tls, dataset)
        if rsrc.type != truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME:
            return None

        props = rsrc.get_properties(properties={
            truenas_pylibzfs.ZFSProperty.VOLSIZE,
            truenas_pylibzfs.ZFSProperty.REFRESERVATION,
        })
        volsize = _prop_int(props.volsize)
        refreservation = _prop_int(props.refreservation)
    except (ZFSPathNotFoundException, truenas_pylibzfs.ZFSException, RuntimeError):
        # A property that cannot be read is no reason to refuse a rollback that
        # would otherwise go ahead, so the refreservation is simply left as it is.
        logger.warning(
            "%s: could not be inspected for a refreservation to restore after the rollback",
            dataset,
            exc_info=True,
        )
        return None

    # The equality gate follows zfs_rollback(), which restores the refreservation only
    # when it exactly covered the volsize beforehand. Volumes the middleware creates set
    # refreservation to the literal volsize, so they qualify; one created by
    # `zfs create -V` carries a larger synthetic refreservation (volsize times copies,
    # plus metadata overhead) and is deliberately left alone, as zfs(8) leaves it.
    if volsize != refreservation:
        return None
    return volsize


def _restore_volume_reservation(tls: Any, dataset: str, old_volsize: int) -> None:
    """Re-set the ``refreservation`` of ``dataset`` when the rollback changed its volsize."""
    try:
        rsrc = open_resource(tls, dataset)
        props = rsrc.get_properties(properties={truenas_pylibzfs.ZFSProperty.VOLSIZE})
        new_volsize = _prop_int(props.volsize)
        if new_volsize == old_volsize:
            return
        with _tolerate_history_write_failure(f"refreservation update of {dataset!r}"):
            rsrc.set_properties(properties={"refreservation": str(new_volsize)})
    except (ZFSPathNotFoundException, truenas_pylibzfs.ZFSException, RuntimeError):
        logger.warning(
            "%s: rolled back, but its refreservation could not be restored to match the new volsize; "
            "the volume is now thin provisioned",
            dataset,
            exc_info=True,
        )
