# -*- coding=utf-8 -*-
"""Cross-version API changelog computation.

Given two adjacent :class:`APIDump` objects, produce a :class:`Changelog`
describing which methods/events were added, removed, or had their schemas
changed. The schema diff is intentionally shallow (top-level call parameters
and return value) — deeper changes are surfaced as a generic note pointing the
reader at the per-method page.
"""
from __future__ import annotations

import dataclasses
import typing

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.doc import APIDump, APIDumpMethod, APIDumpEvent


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
    events_added: list[str] = dataclasses.field(default_factory=list)
    events_removed: list[str] = dataclasses.field(default_factory=list)
    events_changed: list[SchemaChange] = dataclasses.field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.methods_added or self.methods_removed or self.methods_changed or
            self.events_added or self.events_removed or self.events_changed
        )


def _type_summary(schema: dict) -> str:
    """Render a brief human-readable type summary for a JSON-Schema fragment."""
    if not isinstance(schema, dict):
        return "unknown"

    for combiner in ("anyOf", "oneOf"):
        if combiner in schema:
            return " | ".join(_type_summary(s) for s in schema[combiner])

    t = schema.get("type")
    if isinstance(t, list):
        return " | ".join(t)
    if t:
        return t
    if "enum" in schema:
        return "enum"
    if "const" in schema:
        return "const"
    return "unknown"


def _diff_object_properties(old: dict, new: dict, label: str) -> list[str]:
    """Diff top-level properties of two object schemas. `label` is e.g. `parameter` or `field`."""
    old_props = old.get("properties", {}) if isinstance(old, dict) else {}
    new_props = new.get("properties", {}) if isinstance(new, dict) else {}
    lines = []
    for name in sorted(set(new_props) - set(old_props)):
        lines.append(f"added {label} `{name}`")
    for name in sorted(set(old_props) - set(new_props)):
        lines.append(f"removed {label} `{name}`")
    for name in sorted(set(old_props) & set(new_props)):
        old_type = _type_summary(old_props[name])
        new_type = _type_summary(new_props[name])
        if old_type != new_type:
            lines.append(f"{label} `{name}` type changed ({old_type} → {new_type})")
    return lines


def _diff_call_parameters(old: dict, new: dict) -> list[str]:
    """Brief top-level diff of the `Call parameters` array schema."""
    old_items = old.get("prefixItems", []) if isinstance(old, dict) else []
    new_items = new.get("prefixItems", []) if isinstance(new, dict) else []
    old_by_name = {item.get("title"): item for item in old_items if isinstance(item, dict)}
    new_by_name = {item.get("title"): item for item in new_items if isinstance(item, dict)}

    lines = []
    for name in sorted(k for k in new_by_name if k not in old_by_name and k is not None):
        lines.append(f"added parameter `{name}`")
    for name in sorted(k for k in old_by_name if k not in new_by_name and k is not None):
        lines.append(f"removed parameter `{name}`")
    for name in sorted(k for k in new_by_name if k in old_by_name and k is not None):
        old_type = _type_summary(old_by_name[name])
        new_type = _type_summary(new_by_name[name])
        if old_type != new_type:
            lines.append(f"parameter `{name}` type changed ({old_type} → {new_type})")
    return lines


def _diff_return_value(old: dict, new: dict) -> list[str]:
    """Brief top-level diff of the `Return value` schema."""
    old_type = _type_summary(old) if isinstance(old, dict) else "unknown"
    new_type = _type_summary(new) if isinstance(new, dict) else "unknown"
    if old_type != new_type:
        return [f"return value type changed ({old_type} → {new_type})"]
    if isinstance(old, dict) and isinstance(new, dict) and old.get("type") == "object":
        return _diff_object_properties(old, new, "field")
    return []


def compute_schema_diff(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """Compare two method/event schemas. Returns (call_params_diff, return_value_diff)."""
    if old == new:
        return [], []

    old_props = old.get("properties", {}) if isinstance(old, dict) else {}
    new_props = new.get("properties", {}) if isinstance(new, dict) else {}

    call_diff = _diff_call_parameters(
        old_props.get("Call parameters", {}),
        new_props.get("Call parameters", {}),
    )
    return_diff = _diff_return_value(
        old_props.get("Return value", {}),
        new_props.get("Return value", {}),
    )
    return call_diff, return_diff


def _diff_items(
    previous: typing.Iterable[APIDumpMethod | APIDumpEvent], current: typing.Iterable[APIDumpMethod | APIDumpEvent],
) -> tuple[list[str], list[str], list[SchemaChange]]:
    """Compute added/removed/changed for a list of APIDumpMethod or APIDumpEvent."""
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
    events_added, events_removed, events_changed = _diff_items(previous.events, current.events)
    return Changelog(
        previous_version=previous.version,
        methods_added=methods_added,
        methods_removed=methods_removed,
        methods_changed=methods_changed,
        events_added=events_added,
        events_removed=events_removed,
        events_changed=events_changed,
    )
