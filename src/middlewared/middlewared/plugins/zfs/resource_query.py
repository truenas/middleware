from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
import errno
import pathlib
from typing import TYPE_CHECKING, Any

from truenas_pylibzfs import ZFSProperty

from middlewared.api.current import (
    ZFSResourceQuery,
    ZFSResourceQueryExtra,
    ZFSResourceQueryOptions,
    ZFSResourceSnapshotCountQuery,
    ZFSResourceSnapshotQuery,
)
from middlewared.service_exception import ValidationError
from middlewared.utils.filter_list import filter_list

from .exceptions import ZFSPathNotFoundException
from .property_management import PROPERTY_TEMPLATES
from .query_impl import query_impl as _raw_query
from .utils import reject_overlapping_paths

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.query"


def validate_query_args(data: ZFSResourceQuery) -> None:
    for path in data.paths:
        if "@" in path:
            raise ValidationError(
                SCHEMA,
                "Use `zfs.resource.snapshot.query` to query snapshot information.",
            )

    if data.get_children or data.max_depth > 0:
        reject_overlapping_paths(SCHEMA, data.paths, "get_children")


def nest_paths(flat_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach each node to its nearest existing ancestor, returning the root nodes.

    Two passes are needed because the input is not guaranteed to arrive in
    hierarchical order. A node with no ancestor present becomes a root itself.
    """
    node_map = {}
    roots = []
    for item in flat_list:
        item.setdefault("children", [])
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


def identity_paths(filters: Sequence[Sequence[Any]]) -> list[str] | None:
    """The paths named by the first top-level ``id``/``name`` filter, or ``None`` when there is none.

    Values containing ``@`` are dropped: no filesystem or volume can carry such a name.
    """
    for f in filters:
        if len(f) != 3:
            continue
        key, op, value = f
        if key not in ("id", "name"):
            continue
        if op == "=" and isinstance(value, str):
            values: list[str] = [value]
        elif op == "in" and isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
            values = list(value)
        else:
            continue
        return [path for path in dict.fromkeys(values) if "@" not in path]
    return None


def _walk_filter_keys(filters: Sequence[Sequence[Any]], visit: Callable[[Any], None]) -> None:
    for f in filters:
        if len(f) == 2 and f[0] == "OR":
            _walk_filter_keys(f[1], visit)
        elif f and isinstance(f[0], list):
            _walk_filter_keys(f, visit)
        elif len(f) == 3:
            visit(f[0])


def referenced_properties(
    filters: Sequence[Sequence[Any]], select: Sequence[str | Sequence[Any]]
) -> tuple[set[str], bool]:
    """The ZFS properties ``filters`` and ``select`` refer to, and whether any of them refers to a source."""
    names: set[str] = set()
    needs_source = False

    def visit(key: Any) -> None:
        nonlocal needs_source
        if not isinstance(key, str):
            return
        parts = key.split(".")
        if len(parts) < 2 or parts[0] != "properties":
            return
        names.add(parts[1])
        if len(parts) > 2 and parts[2] == "source":
            needs_source = True

    _walk_filter_keys(filters, visit)
    for entry in select:
        visit(entry[0] if isinstance(entry, (list, tuple)) else entry)

    for name in names:
        try:
            ZFSProperty[name.upper()]
        except KeyError:
            raise ValidationError(f"{SCHEMA}.filters", f"{name!r} is not a ZFS property", errno.EINVAL) from None

    return names, needs_source


def _merge_properties(requested: list[str] | None, referenced: set[str]) -> list[str] | None:
    if not referenced:
        return requested
    if requested is None:
        return sorted(referenced)
    if not requested:
        return sorted({prop.name.lower() for prop in PROPERTY_TEMPLATES.default} | referenced)
    return sorted(set(requested) | referenced)


def build_private_query(
    filters: Sequence[Sequence[Any]], options: ZFSResourceQueryOptions
) -> ZFSResourceQuery | None:
    """Translate the public query arguments into the private query, or ``None`` when nothing can match."""
    extra: ZFSResourceQueryExtra = options.extra
    referenced, needs_source = referenced_properties(filters, options.select)
    common: dict[str, Any] = {
        "properties": _merge_properties(extra.properties, referenced),
        "get_user_properties": extra.get_user_properties,
        "get_source": extra.get_source or needs_source,
        "get_tier": extra.get_tier,
        "get_crypto": extra.get_crypto,
        "get_snapshot_count": extra.get_snapshot_count,
        "get_snapshots": extra.get_snapshots,
        "snapshots_properties": extra.snapshots_properties,
        "exclude_internal_paths": extra.exclude_internal_paths,
    }

    identity = identity_paths(filters)
    if identity is not None:
        if not identity:
            return None
        return ZFSResourceQuery(
            paths=identity,
            # An identity filter can only match the named paths, so descending into their children is
            # wasted work.
            get_children=False,
            max_depth=0,
            # Paths synthesised from a filter must not unhide internal datasets the way a path the caller
            # named explicitly does.
            allow_internal_paths=False,
            **common,
        )

    return ZFSResourceQuery(
        paths=extra.paths,
        get_children=extra.get_children,
        max_depth=extra.max_depth,
        **common,
    )


def _count_snapshots(context: ServiceContext, paths: list[str]) -> dict[str, int]:
    return context.call_sync2(
        context.s.zfs.resource.snapshot.count_impl,
        ZFSResourceSnapshotCountQuery(paths=paths, recursive=False),
    )


def _query_snapshots(
    context: ServiceContext, paths: list[str], properties: list[str] | None
) -> list[dict[str, Any]]:
    return context.call_sync2(
        context.s.zfs.resource.snapshot.query_impl,
        ZFSResourceSnapshotQuery(paths=paths, recursive=False, properties=properties),
    )


def _annotate_snapshot_counts(context: ServiceContext, rows: list[dict[str, Any]]) -> None:
    paths = [row["name"] for row in rows]
    if not paths:
        return

    try:
        counts = _count_snapshots(context, paths)
    except ZFSPathNotFoundException:
        counts = {}
        for path in paths:
            try:
                counts.update(_count_snapshots(context, [path]))
            except ZFSPathNotFoundException:
                continue

    for row in rows:
        row["snapshot_count"] = counts.get(row["name"])


def _annotate_snapshots(
    context: ServiceContext, rows: list[dict[str, Any]], properties: list[str] | None
) -> None:
    paths = [row["name"] for row in rows]
    if not paths:
        return

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missed: set[str] = set()
    try:
        snapshots = _query_snapshots(context, paths, properties)
    except ZFSPathNotFoundException:
        snapshots = []
        for path in paths:
            try:
                snapshots.extend(_query_snapshots(context, [path], properties))
            except ZFSPathNotFoundException:
                missed.add(path)

    for snapshot in snapshots:
        grouped[snapshot["dataset"]].append(snapshot)

    for row in rows:
        row["snapshots"] = None if row["name"] in missed else grouped[row["name"]]


def query_impl(context: ServiceContext, tls: Any, data: ZFSResourceQuery) -> list[dict[str, Any]]:
    validate_query_args(data)

    tier_enabled = False
    if data.get_tier:
        tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled

    results = _raw_query(tls.lzh, data.model_dump(), tier_enabled=tier_enabled)
    if data.get_snapshot_count:
        _annotate_snapshot_counts(context, results)
    if data.get_snapshots:
        _annotate_snapshots(context, results, data.snapshots_properties)

    if data.nest_results:
        return nest_paths(results)
    else:
        return results


def query(
    context: ServiceContext, filters: Sequence[Sequence[Any]], options: ZFSResourceQueryOptions
) -> list[dict[str, Any]] | dict[str, Any] | int:
    data = build_private_query(filters, options)
    rows: list[dict[str, Any]] = []
    if data is not None:
        rows = context.call_sync2(context.s.zfs.resource.query_impl, data)
    return filter_list(rows, filters, options.model_dump())
