from __future__ import annotations

import errno
import pathlib
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ZFSResourceEntry, ZFSResourceQuery
from middlewared.service_exception import ValidationError

from .exceptions import ZFSPathNotFoundException
from .query_impl import query_impl as _raw_query
from .utils import reject_overlapping_paths

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def validate_query_args(data: ZFSResourceQuery) -> None:
    for path in data.paths:
        if "@" in path:
            raise ValidationError(
                "zfs.resource.query",
                "Use `zfs.resource.snapshot.query` to query snapshot information.",
            )

    if data.get_children:
        reject_overlapping_paths("zfs.resource.query", data.paths, "get_children")


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
                node_map[pap]["children"].append(item)
                break
        else:
            roots.append(item)
    return roots


def query_impl(context: ServiceContext, tls: Any, data: ZFSResourceQuery) -> list[dict[str, Any]]:
    validate_query_args(data)

    tier_enabled = False
    if data.get_tier:
        tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled

    results = _raw_query(tls.lzh, data.model_dump(), tier_enabled=tier_enabled)
    if data.nest_results:
        return nest_paths(results)
    else:
        return results


def query(context: ServiceContext, data: ZFSResourceQuery) -> list[ZFSResourceEntry]:
    try:
        return [
            ZFSResourceEntry(**resource) for resource in context.call_sync2(context.s.zfs.resource.query_impl, data)
        ]
    except ZFSPathNotFoundException as e:
        raise ValidationError("zfs.resource.query", e.message, errno.ENOENT)
