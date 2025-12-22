import dataclasses
import errno
from typing import TypedDict

from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathInvalidException,
    ZFSPathNotFoundException,
)
from .snapshot_query_impl import query_snapshots_impl

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None


__all__ = ("create_snapshots_impl", "CreateSnapshotArgs")


class CreateSnapshotArgs(TypedDict, total=False):
    dataset: str
    """The dataset path to snapshot (e.g., 'pool/dataset')."""
    name: str
    """The snapshot name (the part after @)."""
    recursive: bool
    """Create snapshots recursively for child datasets."""
    exclude: list[str]
    """Datasets to exclude when creating recursive snapshots."""
    user_properties: dict[str, str]
    """User properties to set on the snapshot."""


@dataclasses.dataclass(slots=True, kw_only=True)
class CollectDatasetsState:
    datasets: list
    exclude: set


def __collect_datasets_callback(child_hdl, state: CollectDatasetsState) -> bool:
    """Callback for collecting child dataset names recursively."""
    name = child_hdl.name
    if name not in state.exclude:
        state.datasets.append(name)
        # Recurse into children
        child_hdl.iter_filesystems(callback=__collect_datasets_callback, state=state)
    return True


def _collect_child_datasets(ds_hdl, exclude: set[str]) -> list[str]:
    """Collect all child dataset names recursively.

    Args:
        ds_hdl: Dataset handle from pylibzfs
        exclude: Set of dataset names to exclude

    Returns:
        List of child dataset names (not including the parent)
    """
    state = CollectDatasetsState(datasets=[], exclude=exclude)
    ds_hdl.iter_filesystems(callback=__collect_datasets_callback, state=state)
    return state.datasets


def create_snapshots_impl(tls, data: CreateSnapshotArgs) -> dict:
    """Create ZFS snapshot(s).

    Args:
        tls: Thread local storage containing lzh (libzfs handle)
        data: Create parameters

    Returns:
        Snapshot entry dict for the primary snapshot created

    Raises:
        ZFSPathNotFoundException: If the dataset doesn't exist
        ZFSPathAlreadyExistsException: If snapshot already exists
        ZFSPathInvalidException: If no datasets to snapshot (all excluded)
        ZFSCoreException: If snapshot creation fails
    """
    dataset = data["dataset"]
    snap_name = data["name"]
    recursive = data.get("recursive", False)
    exclude = set(data.get("exclude", []))
    user_properties = data.get("user_properties")

    # Build list of datasets to snapshot
    datasets_to_snap = []

    # Open the primary dataset to verify it exists
    try:
        ds_hdl = tls.lzh.open_resource(name=dataset)
    except truenas_pylibzfs.ZFSException as e:
        if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(dataset)
        raise

    # Add primary dataset if not excluded
    if dataset not in exclude:
        datasets_to_snap.append(dataset)

    # Collect child datasets if recursive
    if recursive:
        child_datasets = _collect_child_datasets(ds_hdl, exclude)
        datasets_to_snap.extend(child_datasets)

    if not datasets_to_snap:
        raise ZFSPathInvalidException(
            f"No datasets to snapshot - '{dataset}' and all children are excluded"
        )

    # Build snapshot names: "{dataset}@{name}"
    snapshot_names = [f"{ds}@{snap_name}" for ds in datasets_to_snap]

    # Create the snapshots
    # Note: lzc.create_snapshots is atomic - all succeed or all fail
    kwargs = {"snapshot_names": snapshot_names}
    if user_properties:
        kwargs["user_properties"] = user_properties

    try:
        truenas_pylibzfs.lzc.create_snapshots(**kwargs)
    except truenas_pylibzfs.lzc.ZFSCoreException as e:
        # errors is tuple of (snapshot_path, error_code) pairs
        for snap_path, err_code in e.errors:
            if err_code == errno.EEXIST:
                raise ZFSPathAlreadyExistsException(snap_path)
        raise

    # Query and return the primary snapshot
    # The requested properties are expected by UI
    primary_snap_path = f"{dataset}@{snap_name}"
    results = query_snapshots_impl(
        tls.lzh,
        {"paths": [primary_snap_path], "properties": ["creation", "createtxg"]},
    )

    # TODO: Consider returning list of all created snapshots for recursive=True
    # Currently returns only the primary snapshot entry
    if results:
        return results[0]

    # Shouldn't happen if create succeeded, but handle gracefully
    return {
        "name": primary_snap_path,
        "pool": dataset.split("/")[0],
        "dataset": dataset,
        "snapshot_name": snap_name,
        "type": "SNAPSHOT",
        "createtxg": 0,
        "guid": 0,
        "properties": {},
        "user_properties": {},
    }
