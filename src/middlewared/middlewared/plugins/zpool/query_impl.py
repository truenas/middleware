import time
import typing

from middlewared.utils import BOOT_POOL_NAME_VALID

from truenas_pylibzfs import libzfs_types, property_sets, ZFSException, ZFSError, ZPOOLProperty

from .exceptions import ZpoolNotFoundException
from .get_zpool_features_impl import get_zpool_features_impl

__all__ = ("query_impl",)


def _convert_vdev_state(vdev: dict) -> None:
    """Recursively convert VDevState enums to strings and children tuples to lists."""
    vdev["state"] = vdev["state"].name
    if vdev["children"]:
        vdev["children"] = list(vdev["children"])
        for child in vdev["children"]:
            _convert_vdev_state(child)
    else:
        vdev["children"] = []


def _format_topology(status_dict: dict) -> dict:
    """Organize vdevs from a pylibzfs status dict into a topology dict.

    Separates storage vdevs into 'data' (groups with children) and 'stripe'
    (single-disk vdevs without children), and places support vdevs (cache,
    dedup, log, special) and spares into their respective keys.

    Also converts VDevState enums to strings and children tuples to lists
    via _convert_vdev_state.

    Args:
        status_dict: The dict returned by pool.status(asdict=True), containing
            'storage_vdevs', 'support_vdevs', and 'spares' keys.

    Returns:
        dict with keys: cache, data, dedup, log, spares, special, stripe.
        Each value is a list of vdev dicts.
    """
    top = {
        "cache": [],
        "data": [],
        "dedup": [],
        "log": [],
        "spares": [],
        "special": [],
        "stripe": [],
    }
    for vdev in status_dict["storage_vdevs"]:
        _convert_vdev_state(vdev)
        if vdev["children"]:
            top["data"].append(vdev)
        else:
            top["stripe"].append(vdev)

    for key in ("cache", "dedup", "log", "special"):
        for vdev in status_dict["support_vdevs"][key]:
            _convert_vdev_state(vdev)
            top[key].append(vdev)

    for vdev in status_dict["spares"]:
        _convert_vdev_state(vdev)
        top["spares"].append(vdev)

    return top


def _format_scan(s: libzfs_types.struct_zpool_scrub | None) -> dict | None:
    """Transform a struct_zpool_scrub into a scan dict, or None.

    Args:
        s: A truenas_pylibzfs.struct_zpool_scrub or None.

    Returns:
        dict with keys: function, state, start_time, end_time, percentage,
        bytes_to_process, bytes_processed, bytes_issued, pause, errors,
        total_secs_left.  Returns None when no scan has ever run.
    """
    if s is None:
        return None

    is_scanning = s.state.name == "SCANNING"

    # percentage — use the pre-computed value when available (active scan),
    # otherwise derive from issued / (to_examine - skipped).
    percentage = s.percentage
    if percentage is None:
        total = s.to_examine - s.skipped
        percentage = (s.issued / total) * 100 if total > 0 else 0.0

    # total_secs_left — only meaningful while actively scanning.
    total_secs_left = None
    if is_scanning:
        total = s.to_examine - s.skipped
        elapsed = (int(time.time()) - s.pass_start - s.pass_scrub_spent_paused) or 1
        issue_rate = (s.pass_issued or 1) / elapsed
        total_secs_left = int((total - s.issued) / issue_rate)

    # pause — unix timestamp when the scan was paused (0 = not paused).
    # Only meaningful while actively scanning and paused.
    pause = s.pass_scrub_pause if is_scanning and s.pass_scrub_pause != 0 else None

    return {
        "function": s.func.name,
        "state": s.state.name,
        "start_time": s.start_time,
        "end_time": s.end_time if not is_scanning else None,
        "percentage": percentage,
        "bytes_to_process": s.to_examine,
        "bytes_processed": s.examined,
        "bytes_issued": s.issued,
        "pause": pause,
        "errors": s.errors,
        "total_secs_left": total_secs_left,
    }


def _format_expand(e: libzfs_types.struct_zpool_expand | None) -> dict | None:
    """Transform a struct_zpool_expand into an expansion dict, or None.

    Args:
        e: A truenas_pylibzfs.struct_zpool_expand or None.

    Returns:
        dict with keys: state, expanding_vdev, start_time, end_time,
        bytes_to_reflow, bytes_reflowed, waiting_for_resilver,
        total_secs_left, percentage. Returns None when no expansion
        has ever run (expand_info() returned None).
    """
    if e is None:
        return None

    is_scanning = e.state.name == "SCANNING"

    total = e.to_reflow or 1
    percentage = (e.reflowed / total) * 100

    total_secs_left = None
    if is_scanning:
        elapsed = (time.time() - e.start_time) or 1
        rate = (e.reflowed or 1) / elapsed
        total_secs_left = int((total - e.reflowed) / rate)

    return {
        "state": e.state.name,
        "expanding_vdev": e.expanding_vdev,
        "start_time": e.start_time,
        "end_time": e.end_time if not is_scanning else None,
        "bytes_to_reflow": e.to_reflow,
        "bytes_reflowed": e.reflowed,
        "waiting_for_resilver": e.waiting_for_resilver,
        "total_secs_left": total_secs_left,
        "percentage": percentage,
    }


def _format_properties(props_struct: libzfs_types.struct_zpool_property, requested_names: list[str]) -> dict:
    """Transform struct_zpool_property to a dict of property value dicts."""
    result = {}
    for name in requested_names:
        prop = getattr(props_struct, name, None)
        if prop is not None:
            result[name] = {
                "raw": prop.raw,
                "source": prop.source.name if prop.source is not None else None,
                "value": prop.value,
            }
    return result


def _format_features(features_dict: dict[str, libzfs_types.struct_zpool_feature]) -> list[dict]:
    """Transform dict[str, struct_zpool_feature] to a list of feature dicts."""
    rv = list()
    for name, feat in features_dict.items():
        rv.append(
            {
                "name": name,
                "guid": feat.guid,
                "description": feat.description,
                "state": feat.state,
            }
        )
    return rv


def _build_pool_dict(pool: libzfs_types.ZFSPool, lzh: libzfs_types.ZFS, data: dict) -> dict:
    """Build a pool dict from pylibzfs pool object.

    Args:
        pool: An already-opened pylibzfs pool object.
        lzh: The libzfs handle.
        data: Query parameters (pool_names, properties, topology, scan, expand, features).

    Returns:
        A dict matching the ZPoolEntry schema.
    """
    # Single status() call — used for both health info and topology
    follow_links = data.get("follow_links", True)
    full_path = data.get("full_path", True)
    status_dict = pool.status(asdict=True, follow_links=follow_links, full_path=full_path)
    zpool_status = status_dict["status"]
    is_nonrecoverable = zpool_status in property_sets.ZPOOL_STATUS_NONRECOVERABLE
    health = pool.get_properties(properties={ZPOOLProperty.HEALTH}).health.value
    result: dict[str, typing.Any] = {
        "name": pool.name,
        "guid": status_dict["guid"],
        "status": health,
        "healthy": not is_nonrecoverable and health == "ONLINE",
        "warning": zpool_status in property_sets.ZPOOL_STATUS_RECOVERABLE,
        "status_code": zpool_status.name.removeprefix("ZPOOL_STATUS_"),
        "status_detail": status_dict["reason"],
    }
    # Properties
    prop_names = data.get("properties", [])
    if prop_names:
        enum_set = set()
        for n in prop_names:
            try:
                enum_set.add(ZPOOLProperty[n.upper()])
            except KeyError:
                pass

        if enum_set:
            props_struct = pool.get_properties(properties=enum_set)
            result["properties"] = _format_properties(props_struct, prop_names)
        else:
            result["properties"] = {}
    else:
        result["properties"] = None

    result["topology"] = None
    if data.get("topology"):
        result["topology"] = _format_topology(status_dict)

    result["scan"] = None
    if data.get("scan"):
        result["scan"] = _format_scan(pool.scrub_info())

    result["expand"] = None
    if data.get("expand"):
        result["expand"] = _format_expand(pool.expand_info())

    result["features"] = None
    if data.get("features"):
        result["features"] = _format_features(get_zpool_features_impl(lzh, pool.name))

    return result


def _get_zpools_cb(pool, state: list):
    """Callback for iter_pools that collects non-boot pool names.

    Appends pool names to `state`, skipping any pool whose name matches
    a known boot pool name (e.g. 'boot-pool'). Returns True to continue
    iteration.
    """
    if pool.name in BOOT_POOL_NAME_VALID:
        # Skip boot pool during discovery. Callers that need boot pool
        # info should explicitly pass its name via pool_names.
        return True
    state.append(pool.name)
    return True


def query_impl(
    lzh: libzfs_types.ZFS,
    data: dict,
    return_pool_obj: bool = False
) -> list[dict] | list[tuple[dict, libzfs_types.ZFSPool]]:
    """Query zpools status.

    Args:
        lzh: pylibzfs handle (from tls.lzh or truenas_pylibzfs.open_handle()).
        data: dict with keys matching ZPoolQuery fields:
            pool_names, properties, topology, scan, expand, features.
        return_pool_obj: bool when set to True will return the open_pool()
            object from truenas_pylibzfs. This is for internal callers only
            to prevent unnecessary open_pool() calls within a single function.
    Returns:
        list[dict] matching ZPoolEntry schema.
    """
    pool_names = data.get("pool_names")
    if pool_names is None:
        pool_names = []
        lzh.iter_pools(callback=_get_zpools_cb, state=pool_names)

    results = []
    for name in pool_names:
        try:
            pool = lzh.open_pool(name=name)
            rv = _build_pool_dict(pool, lzh, data)
            if return_pool_obj:
                results.append((rv, pool))
            else:
                results.append(rv)
        except ZFSException as e:
            if e.code == ZFSError.EZFS_NOENT:
                if data.get("raise_on_noent", False):
                    raise ZpoolNotFoundException(name) from None
                else:
                    continue
            raise
    return results
