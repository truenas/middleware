import dataclasses

from truenas_pylibzfs import ZFSError, ZFSException, ZFSType

from .exceptions import ZFSPathNotFoundException
from .property_management import build_set_of_zfs_snapshot_props, DeterminedProperties
from .utils import has_internal_path

__all__ = ("query_snapshots_impl",)


@dataclasses.dataclass(slots=True, kw_only=True)
class SnapshotQueryState:
    results: list
    query_args: dict
    dp: DeterminedProperties
    parent_type: ZFSType
    eip: bool
    """(e)xclude (i)nternal (p)aths. Unless someone is querying
    an internal path, we will exclude them."""


def __normalize_snapshot_result(data: dict, *, normalize_source: bool) -> dict:
    """Normalize snapshot result from asdict().

    Adds dataset and snapshot_name fields parsed from the full name,
    and normalizes the type field.
    """
    # Remove internal fields
    data.pop("type_enum", None)
    data.pop("crypto", None)

    # Normalize type: "ZFS_TYPE_SNAPSHOT" -> "SNAPSHOT"
    data["type"] = data["type"].removeprefix("ZFS_TYPE_")

    # Parse dataset and snapshot_name from full name (e.g., "pool/dataset@snap")
    full_name = data["name"]
    if "@" in full_name:
        dataset, snapshot_name = full_name.split("@", 1)
        data["dataset"] = dataset
        data["snapshot_name"] = snapshot_name
    else:
        data["dataset"] = full_name
        data["snapshot_name"] = ""

    # Normalize property sources if requested
    if normalize_source and data.get("properties"):
        for prop_value in data["properties"].values():
            if "source" in prop_value and prop_value["source"]:
                prop_value["source"]["type"] = prop_value["source"]["type"].name

    return data


def __snapshot_callback(snap_hdl, state: SnapshotQueryState) -> bool:
    """Callback for each snapshot during iteration.

    Returns True to continue iteration, False to stop.
    """
    snap_name = snap_hdl.name

    # Check if internal path should be excluded
    if state.eip and has_internal_path(snap_name):
        return True

    # Apply txg filtering
    createtxg = snap_hdl.createtxg
    min_txg = state.query_args["min_txg"]
    max_txg = state.query_args["max_txg"]

    if min_txg and createtxg < min_txg:
        return True
    if max_txg and createtxg > max_txg:
        return True

    # Get snapshot data with type-specific properties
    get_source = state.query_args["get_source"]
    properties = build_set_of_zfs_snapshot_props(
        state.parent_type,
        state.dp,
        state.query_args.get("properties"),
    )
    info = snap_hdl.asdict(
        properties=properties,
        get_user_properties=state.query_args["get_user_properties"],
        get_source=get_source,
    )
    if state.query_args["get_holds"]:
        info["holds"] = snap_hdl.get_holds() or None
    else:
        info["holds"] = None

    # Normalize the result
    info = __normalize_snapshot_result(info, normalize_source=get_source)

    state.results.append(info)
    return True


def __dataset_iter_callback(ds_hdl, state: SnapshotQueryState) -> bool:
    """Callback for iterating over datasets to get their snapshots.

    Returns True to continue iteration, False to stop.
    """
    ds_name = ds_hdl.name

    # Check if internal path should be excluded
    if state.eip and has_internal_path(ds_name):
        return True

    # Set parent type for snapshot property resolution
    state.parent_type = ds_hdl.type

    # Iterate over this dataset's snapshots
    ds_hdl.iter_snapshots(callback=__snapshot_callback, state=state, fast=True)

    # If recursive, also iterate child datasets
    if state.query_args["recursive"]:
        ds_hdl.iter_filesystems(callback=__dataset_iter_callback, state=state)

    return True


def __should_exclude_internal_paths(data: dict) -> bool:
    """Determine if internal paths should be excluded from results."""
    for path in data.get("paths", []):
        if has_internal_path(path):
            # Someone is explicitly querying an internal path
            return False
    # Exclude internal paths by default
    return data.get("exclude_internal_paths", True)


def __query_snapshot_directly(hdl, snap_path: str, state: SnapshotQueryState) -> None:
    """Query a specific snapshot by its full path (pool/dataset@snapshot).

    Opens the parent dataset to determine its type for proper property handling.
    """
    # Parse dataset name from snapshot path
    dataset_name = snap_path.split("@")[0]

    try:
        # Open parent dataset to get its type
        ds_hdl = hdl.open_resource(name=dataset_name)
        state.parent_type = ds_hdl.type

        # Now open and process the snapshot
        snap_hdl = hdl.open_resource(name=snap_path)
        __snapshot_callback(snap_hdl, state)
    except ZFSException as e:
        if ZFSError(e.code) == ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(snap_path)
        raise


def __query_dataset_snapshots(hdl, ds_path: str, state: SnapshotQueryState) -> None:
    """Query all snapshots for a dataset (and optionally its children)."""
    try:
        ds_hdl = hdl.open_resource(name=ds_path)
        __dataset_iter_callback(ds_hdl, state)
    except ZFSException as e:
        if ZFSError(e.code) == ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(ds_path)
        raise


def query_snapshots_impl(hdl, data: dict) -> list:
    """Query ZFS snapshots with filtering options.

    Args:
        hdl: ZFS library handle (tls.lzh)
        data: Query parameters dict containing:
            - paths: List of dataset or snapshot paths to query
            - properties: List of property names to retrieve (None/[] = none)
            - min_txg: Minimum transaction group filter
            - max_txg: Maximum transaction group filter
            - get_user_properties: Whether to include user properties
            - get_source: Whether to include property source info
            - recursive: Whether to include child dataset snapshots
            - get_holds: Whether to include holds info

    Returns:
        List of snapshot dictionaries
    """
    # Set defaults to avoid repeated .get() in callbacks
    data.setdefault("min_txg", 0)
    data.setdefault("max_txg", 0)
    data.setdefault("get_user_properties", False)
    data.setdefault("get_source", False)
    data.setdefault("recursive", False)
    data.setdefault("get_holds", False)

    state = SnapshotQueryState(
        results=[],
        query_args=data,
        dp=DeterminedProperties(),
        parent_type=None,
        eip=__should_exclude_internal_paths(data),
    )

    paths = data.get("paths", [])

    if paths:
        for path in paths:
            if "@" in path:
                # Direct snapshot query
                __query_snapshot_directly(hdl, path, state)
            else:
                # Dataset path - get all snapshots for this dataset
                __query_dataset_snapshots(hdl, path, state)
    else:
        # No paths specified - query snapshots from root filesystems only
        # User must explicitly set recursive=True to get all snapshots
        hdl.iter_root_filesystems(callback=__dataset_iter_callback, state=state)

    return state.results
