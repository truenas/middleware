import dataclasses
import logging
import os
from typing import Any

from truenas_pylibzfs import ZFSProperty, ZFSType

from middlewared.api.current import ZFSResourceSnapshotCountQuery
from middlewared.service_exception import MatchNotFound
from middlewared.utils.filesystem.constants import ZFSCTL
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBBatchAction,
    TDBBatchOperation,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)

from .utils import has_internal_path, open_resource

__all__ = ("count_snapshots_impl",)

logger = logging.getLogger(__name__)

# TDB cache configuration (same as legacy)
SNAP_COUNT_TDB_NAME = "snapshot_count"
SNAP_COUNT_TDB_OPTIONS = TDBOptions(TDBPathType.PERSISTENT, TDBDataType.JSON)


@dataclasses.dataclass(slots=True, kw_only=True)
class SnapshotCountState:
    counts: dict[str, int]
    """Mapping of dataset names to snapshot counts."""
    batch_ops: list[TDBBatchOperation]
    """Batch operations for TDB cache updates."""
    recursive: bool
    eip: bool
    """(e)xclude (i)nternal (p)aths."""


@dataclasses.dataclass(slots=True)
class SimpleCountState:
    """Simple state for counting snapshots via iter_snapshots."""

    count: int = 0


def __simple_count_callback(snap_hdl: Any, state: SimpleCountState) -> bool:
    """Callback that simply increments the counter."""
    state.count += 1
    return True


def __get_cached_count(cache_key: str) -> dict[str, Any]:
    """Retrieve cached snapshot count from TDB."""
    try:
        with get_tdb_handle(SNAP_COUNT_TDB_NAME, SNAP_COUNT_TDB_OPTIONS) as hdl:
            return hdl.get(cache_key)  # type: ignore
    except MatchNotFound:
        return {"changed_ts": None, "cnt": -1}


def __try_count_via_nlink(ds_hdl: Any) -> int | None:
    """Try to get snapshot count via st_nlink for mounted filesystems.

    This is much faster than iterating snapshots when the dataset is mounted.
    Returns None if the short-circuit cannot be used (unmounted, zvol, etc).
    """
    # Only works for filesystems, not zvols
    if ds_hdl.type != ZFSType.ZFS_TYPE_FILESYSTEM:
        return None

    # Get mountpoint property
    try:
        mp_prop = ds_hdl.get_property(ZFSProperty.MOUNTPOINT)
        if mp_prop is None:
            return None
        mountpoint = mp_prop.value
    except Exception:
        return None

    # Check if actually mounted (not 'none', 'legacy', or '-')
    if not mountpoint or mountpoint in ("none", "legacy", "-"):
        return None

    # Try to stat the .zfs/snapshot directory
    try:
        st = os.stat(f"{mountpoint}/.zfs/snapshot")
        # Verify it's actually the ZFS snapshot control directory
        if st.st_ino == ZFSCTL.INO_SNAPDIR.value:
            return st.st_nlink - 2
    except Exception:
        pass

    return None


def __count_dataset_snapshots_uncached(ds_hdl: Any) -> int:
    """Count snapshots for a single dataset using the most efficient method (no cache)."""
    # Try short-circuit via st_nlink first
    count = __try_count_via_nlink(ds_hdl)
    if count is not None:
        return count

    # Fallback: iterate snapshots (for unmounted datasets and zvols)
    state = SimpleCountState()
    ds_hdl.iter_snapshots(callback=__simple_count_callback, state=state, fast=True)
    return state.count


def __count_dataset_snapshots_cached(ds_hdl: Any, batch_ops: list[TDBBatchOperation]) -> int:
    """Count snapshots with TDB caching using snapshots_changed as invalidation key."""
    ds_name = ds_hdl.name
    cache_key = f"SNAPCNT%{ds_name}"

    # Get snapshots_changed timestamp for cache invalidation
    try:
        sc_prop = ds_hdl.get_property(ZFSProperty.SNAPSHOTS_CHANGED)
        changed_ts = sc_prop.value if sc_prop else None
    except Exception:
        changed_ts = None

    # Check cache
    entry = __get_cached_count(cache_key)

    if entry["changed_ts"] == changed_ts and entry["cnt"] >= 0:
        # Cache hit - return cached count
        return entry["cnt"]  # type: ignore

    # Cache miss - count and update cache
    count = __count_dataset_snapshots_uncached(ds_hdl)

    # Update cache if we have a valid timestamp
    if changed_ts:
        batch_ops.append(
            TDBBatchOperation(
                action=TDBBatchAction.SET,
                key=cache_key,
                value={"changed_ts": changed_ts, "cnt": count},
            )
        )

    return count


def __dataset_count_callback(ds_hdl: Any, state: SnapshotCountState) -> bool:
    """Callback for iterating over datasets to count their snapshots."""
    ds_name = ds_hdl.name

    # Check if internal path should be excluded
    if state.eip and has_internal_path(ds_name):
        return True

    # Count snapshots for this dataset (with caching)
    count = __count_dataset_snapshots_cached(ds_hdl, state.batch_ops)
    state.counts[ds_name] = count

    # If recursive, also iterate child datasets
    if state.recursive:
        ds_hdl.iter_filesystems(callback=__dataset_count_callback, state=state)

    return True


def __should_exclude_internal_paths(data: ZFSResourceSnapshotCountQuery) -> bool:
    """Determine if internal paths should be excluded from counts."""
    for path in data.paths:
        if has_internal_path(path):
            return False
    return True


def __commit_cache_updates(batch_ops: list[TDBBatchOperation]) -> None:
    """Commit batch cache updates to TDB."""
    if not batch_ops:
        return

    try:
        with get_tdb_handle(SNAP_COUNT_TDB_NAME, SNAP_COUNT_TDB_OPTIONS) as hdl:
            hdl.batch_op(batch_ops)
    except Exception:
        logger.warning("Failed to update cached snapshot counts", exc_info=True)


def count_snapshots_impl(tls: Any, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
    """Count ZFS snapshots per dataset.

    Uses TDB caching with snapshots_changed property as invalidation key.
    Falls back to st_nlink short-circuit for mounted filesystems when possible,
    or iter_snapshots for unmounted datasets and zvols.

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        data: Count parameters dict containing:
            - paths: List of dataset paths to count snapshots for
            - recursive: Whether to include child dataset snapshots

    Returns:
        Dict mapping dataset names to their snapshot counts
    """
    state = SnapshotCountState(
        counts={},
        batch_ops=[],
        recursive=data.recursive,
        eip=__should_exclude_internal_paths(data),
    )

    paths = data.paths

    if paths:
        for path in paths:
            rsrc = open_resource(tls, path)
            if rsrc.type == ZFSType.ZFS_TYPE_SNAPSHOT:
                dataset = rsrc.name.split("@", 1)[0]
                state.counts[dataset] = state.counts.get(dataset, 0) + 1
            else:
                __dataset_count_callback(rsrc, state)
    else:
        # No paths specified - count snapshots from root filesystems only
        tls.lzh.iter_root_filesystems(callback=__dataset_count_callback, state=state)

    # Commit any cache updates
    __commit_cache_updates(state.batch_ops)

    return state.counts
