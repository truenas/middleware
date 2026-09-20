from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ZFSResourceEntry, ZFSResourceQuery
from middlewared.service_exception import ValidationError

from .query_impl import query_impl as _raw_query
from .utils import reject_overlapping_paths

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.list"


def validate_query_args(data: ZFSResourceQuery) -> None:
    for path in data.paths:
        if "@" in path:
            raise ValidationError(
                SCHEMA,
                "Use `zfs.resource.snapshot.query` to query snapshot information.",
            )

    # `max_depth > 0` turns the walk on later, so the overlap must be rejected here or the same
    # resource is returned twice.
    if data.get_children or data.max_depth > 0:
        reject_overlapping_paths(SCHEMA, data.paths, "get_children" if data.get_children else "max_depth")


def nest_paths(flat_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach each node to its nearest existing ancestor, returning the root nodes.

    Two passes are needed because the input is not guaranteed to arrive in
    hierarchical order. A node with no ancestor present becomes a root itself.
    """
    node_map = {}
    roots = []
    for item in flat_list:
        node_map[item["name"]] = item
        if item["name"] == item["pool"]:
            roots.append(item)
            continue

    for item in flat_list:
        if item["name"] == item["pool"]:
            continue
        for parent in pathlib.PosixPath(item["name"]).parents:
            pap = parent.as_posix()
            if pap in node_map:
                # An ancestor the walk did not descend into carries `None`, yet a descendant may still
                # have been named explicitly.
                if node_map[pap]["children"] is None:
                    node_map[pap]["children"] = []
                node_map[pap]["children"].append(item)
                break
        else:
            roots.append(item)
    return roots


def list_impl(context: ServiceContext, tls: Any, data: ZFSResourceQuery) -> list[dict[str, Any]]:
    validate_query_args(data)

    tier_enabled = False
    if data.get_tier:
        tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled

    results = _raw_query(tls.lzh, data.model_dump(), tier_enabled=tier_enabled)
    if data.nest_results:
        return nest_paths(results)
    else:
        return results


def list_resources(context: ServiceContext, data: ZFSResourceQuery) -> list[ZFSResourceEntry]:
    return [ZFSResourceEntry(**resource) for resource in context.call_sync2(context.s.zfs.resource.list_impl, data)]
