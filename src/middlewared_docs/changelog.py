# -*- coding=utf-8 -*-
"""Cross-version API changelog computation.

Given two adjacent :class:`APIDump` objects, produce a :class:`Changelog`
describing which methods were added, removed, or had their schemas changed.
The schema diff is intentionally shallow (top-level call parameters and return
value) — deeper changes are surfaced as a generic note pointing the reader at
the per-method page.
"""
from __future__ import annotations

import dataclasses
import typing

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.doc import APIDump, APIDumpMethod


@dataclasses.dataclass
class SchemaChange:
    name: str
    call_params_diff: list[str]
    return_value_diff: list[str]


@dataclasses.dataclass
class Changelog:
    previous_version: str
    methods_added: list[str] = dataclasses.field(default_factory=list)
    methods_removed: list[str] = dataclasses.field(default_factory=list)
    methods_changed: list[SchemaChange] = dataclasses.field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.methods_added or self.methods_removed or self.methods_changed)


def _union_branches(schema: dict) -> list[dict] | None:
    """If `schema` is a oneOf/anyOf, return its branches; else None."""
    for combiner in ("oneOf", "anyOf"):
        if combiner in schema:
            return schema[combiner]


def _branch_name(branch: dict) -> str:
    """Best-effort name for a union branch — prefer Pydantic's `title`, fall back to type."""
    if title := branch.get("title"):
        return title
    return _type_summary(branch)


def _type_summary(schema: dict) -> str:
    """Render a brief human-readable type summary for a JSON-Schema fragment."""
    if not isinstance(schema, dict):
        return "unknown"

    branches = _union_branches(schema)
    if branches is not None:
        return " | ".join(_branch_name(b) for b in branches)

    t = schema.get("type")
    if isinstance(t, list):
        return " | ".join(sorted(t))
    if t:
        return t
    if "enum" in schema:
        return "enum"
    if "const" in schema:
        return "const"
    return "unknown"


def _diff_union(old: dict, new: dict, prefix: str) -> list[str]:
    """Diff two union schemas by branch name. Returns lines describing added/removed variants."""
    old_names = {_branch_name(b) for b in _union_branches(old) or []}
    new_names = {_branch_name(b) for b in _union_branches(new) or []}
    added = [f"{prefix}: added variant `{added}`" for added in sorted(new_names - old_names)]
    removed = [f"{prefix}: removed variant `{removed}`" for removed in sorted(old_names - new_names)]
    return added + removed


def _diff_object_properties(old: dict, new: dict, label: str) -> list[str]:
    """Diff top-level properties of two object schemas. `label` is e.g. `parameter` or `field`."""
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    return [
        f"added {label} `{name}`"
        for name in sorted(set(new_props) - set(old_props))
    ] + [
        f"removed {label} `{name}`"
        for name in sorted(set(old_props) - set(new_props))
    ] + [
        f"{label} `{name}` type changed ({old_type} → {new_type})"
        for name in sorted(set(old_props) & set(new_props))
        if (old_type := _type_summary(old_props[name])) != (new_type := _type_summary(new_props[name]))
    ]


def _diff_call_parameters(old: dict, new: dict) -> list[str]:
    """Brief top-level diff of the `Call parameters` array schema."""
    old_by_name = {item["title"]: item for item in old["prefixItems"]}
    new_by_name = {item["title"]: item for item in new["prefixItems"]}

    lines = [
        f"added parameter `{name}`"
        for name in sorted(new_by_name.keys() - old_by_name.keys())
    ] + [
        f"removed parameter `{name}`"
        for name in sorted(old_by_name.keys() - new_by_name.keys())
    ]

    for name in sorted(new_by_name.keys() & old_by_name.keys()):
        old_param = old_by_name[name]
        new_param = new_by_name[name]
        if _union_branches(old_param) is not None and _union_branches(new_param) is not None:
            union_lines = _diff_union(old_param, new_param, f"parameter `{name}`")
            if union_lines:
                lines.extend(union_lines)
                continue

        old_type = _type_summary(old_param)
        new_type = _type_summary(new_param)
        if old_type != new_type:
            lines.append(f"parameter `{name}` type changed ({old_type} → {new_type})")

    return lines


def _diff_return_value(old: dict, new: dict) -> list[str]:
    """Brief top-level diff of the `Return value` schema."""
    if _union_branches(old) is not None and _union_branches(new) is not None:
        union_lines = _diff_union(old, new, "return value")
        if union_lines:
            return union_lines

    old_type = _type_summary(old)
    new_type = _type_summary(new)
    if old_type != new_type:
        return [f"return value type changed ({old_type} → {new_type})"]
    if old.get("type") == "object":
        return _diff_object_properties(old, new, "field")

    return []


def compute_schema_diff(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """Compare two method/event schemas. Returns (call_params_diff, return_value_diff)."""
    if old == new:
        return [], []

    old_props = old["properties"]
    new_props = new["properties"]

    call_diff = _diff_call_parameters(
        old_props["Call parameters"],
        new_props["Call parameters"],
    )
    return_diff = _diff_return_value(
        old_props["Return value"],
        new_props["Return value"],
    )

    return call_diff, return_diff


def _diff_items(
    previous: typing.Iterable[APIDumpMethod], current: typing.Iterable[APIDumpMethod],
) -> tuple[list[str], list[str], list[SchemaChange]]:
    """Compute added/removed/changed for a list of APIDumpMethod."""
    prev_by_name = {item.name: item for item in previous}
    cur_by_name = {item.name: item for item in current}

    added = sorted(set(cur_by_name) - set(prev_by_name))
    removed = sorted(set(prev_by_name) - set(cur_by_name))
    changed = []
    for name in sorted(set(cur_by_name) & set(prev_by_name)):
        old_schemas = prev_by_name[name].schemas
        new_schemas = cur_by_name[name].schemas
        if old_schemas == new_schemas:
            continue

        call_diff, return_diff = compute_schema_diff(old_schemas, new_schemas)
        if not call_diff and not return_diff:
            # The schemas differ but our shallow diff couldn't surface anything meaningful
            # (e.g. nested-only change). Record the method as changed with a generic note.
            call_diff = []
            return_diff = ["schema changed (see method page for details)"]

        changed.append(SchemaChange(name=name, call_params_diff=call_diff, return_value_diff=return_diff))

    return added, removed, changed


def compute_changelog(previous: APIDump, current: APIDump) -> Changelog:
    methods_added, methods_removed, methods_changed = _diff_items(previous.methods, current.methods)
    return Changelog(
        previous_version=previous.version,
        methods_added=methods_added,
        methods_removed=methods_removed,
        methods_changed=methods_changed,
    )
