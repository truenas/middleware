import typing
from datetime import datetime, timezone

from truenas_pylibzfs import property_sets, ZFSException, ZFSError, ZPOOLProperty

from .exceptions import ZpoolNotFoundException
from .get_zpool_features_impl import get_zpool_features_impl
from .get_zpool_scan_impl import get_zpool_scan_impl

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


def _format_scan(scrub_struct: typing.Any) -> dict | None:
    """Transform struct_zpool_scrub to a scan dict, or None."""
    if scrub_struct is None:
        return None

    percentage = scrub_struct.percentage
    if percentage is None and scrub_struct.to_examine > 0:
        percentage = (scrub_struct.examined / scrub_struct.to_examine) * 100
    if percentage is None:
        percentage = 0.0

    return {
        "function": scrub_struct.func.name,
        "state": scrub_struct.state.name,
        "start_time": datetime.fromtimestamp(scrub_struct.start_time, tz=timezone.utc),
        "end_time": datetime.fromtimestamp(scrub_struct.end_time, tz=timezone.utc),
        "percentage": percentage,
        "bytes_to_process": scrub_struct.to_examine,
        "bytes_processed": scrub_struct.examined,
        "bytes_issued": scrub_struct.issued,
        "pause": None,
        "errors": scrub_struct.errors,
        "total_secs_left": None,
    }


def _format_properties(props_struct: typing.Any, requested_names: list[str]) -> dict:
    """Transform struct_zpool_property to a dict of property value dicts."""
    result = {}
    for name in requested_names:
        prop = getattr(props_struct, name, None)
        if prop is not None:
            result[name] = {
                "raw": prop.raw,
                "source": prop.source.name if prop.source is not None else "NONE",
                "value": prop.value,
            }
    return result


def _format_features(features_dict: dict) -> list[dict]:
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


def _build_pool_dict(pool: typing.Any, lzh: typing.Any, data: dict) -> dict:
    """Build a pool dict from pylibzfs pool object.

    Args:
        pool: An already-opened pylibzfs pool object.
        lzh: The libzfs handle.
        data: Query parameters (pool_names, properties, topology, scan, expand, features).

    Returns:
        A dict matching the ZPoolEntry schema.
    """
    # Single status() call — used for both health info and topology
    status_dict = pool.status(asdict=True)

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

    # Scan
    if data.get("scan"):
        result["scan"] = _format_scan(get_zpool_scan_impl(pool))
    else:
        result["scan"] = None

    result["expand"] = None

    # Features
    if data.get("features"):
        result["features"] = _format_features(get_zpool_features_impl(lzh, pool.name))
    else:
        result["features"] = None

    return result


def _get_zpools_cb(pool, state: list):
    state.append(pool.name)
    return True


def query_impl(lzh: typing.Any, data: dict) -> list[dict]:
    """Query zpools status.

    Args:
        lzh: pylibzfs handle (from tls.lzh or truenas_pylibzfs.open_handle()).
        data: dict with keys matching ZPoolQuery fields:
            pool_names, properties, topology, scan, expand, features.

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
            results.append(_build_pool_dict(pool, lzh, data))
        except ZFSException as e:
            if e.code == ZFSError.EZFS_NOENT:
                if data.get("raise_on_noent", False):
                    raise ZpoolNotFoundException(name)
                else:
                    continue
            raise
    return results
