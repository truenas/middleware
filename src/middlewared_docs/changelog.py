# -*- coding=utf-8 -*-
"""Cross-version API changelog computation.

The diff is semantic, not cosmetic. Description/example wording and
validation-constraint keys (``minLength``, ``pattern``, ...) are never read, so
changes to them produce no changelog entry. The schemas are trusted to follow the
structural rules of the `--dump-api` output.
"""
from __future__ import annotations

import dataclasses
import json
import typing

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.doc import APIDump, APIDumpMethod

_MISSING = object()
# Defaults longer than this are reported without their values.
_MAX_RENDERED_VALUE_LENGTH = 50


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
    """If `schema` is a oneOf/anyOf, return its branches; else None.

    The two combiners are treated identically: a oneOf+discriminator (Pydantic tagged
    union) accepts the same payloads as the equivalent anyOf, so flipping between them
    is not a reportable change.
    """
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
    branches = _union_branches(schema)
    if branches is not None:
        # Deduplicate: unions of similarly-shaped untitled branches would otherwise
        # render as e.g. "any | any | any".
        return " | ".join(dict.fromkeys(_branch_name(branch) for branch in branches))

    if t := schema.get("type"):
        if t == "array" and "prefixItems" in schema:
            return "tuple"
        return t
    if "enum" in schema:
        return "enum"
    if "const" in schema:
        return "const"
    return "any"


def _format_value(value) -> str | None:
    """Render an enum/const/default value for a changelog line; None if too long to inline."""
    rendered = json.dumps(value)
    if len(rendered) > _MAX_RENDERED_VALUE_LENGTH:
        return None
    return rendered


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _map_value_schema(schema: dict) -> dict | None:
    """Schema for an object's undeclared (map) properties; None if they are disallowed.

    Absent `additionalProperties` and `true` both mean "any value" and normalize to the
    bare-any schema `{}` so that flipping between those representations is no change.
    """
    extra = schema.get("additionalProperties", True)
    if extra is False:
        return None
    if extra is True:
        return {}
    return extra


def _group_branches(branches: list[dict]) -> dict[str, list[dict]]:
    """Group union branches by name, preserving order — duplicate names do occur."""
    groups: dict[str, list[dict]] = {}
    for branch in branches:
        groups.setdefault(_branch_name(branch), []).append(branch)
    return groups


class _SchemaDiffer:
    """Recursive schema diff for one tree (the return value or a single call parameter).

    Accumulates change lines in `self.lines`. Lines about the root node itself are
    labeled with `root_label` (empty for the return value, whose label is supplied by
    the renderer); lines about nested nodes are labeled with their `` `<path>` ``.
    """

    def __init__(self, root_path: str, root_label: str):
        self.root_path = root_path
        self.root_label = root_label
        self.lines: list[str] = []

    def _emit(self, path: str, text: str, sep: str = " "):
        label = self.root_label if path == self.root_path else f"`{path}`"
        self.lines.append(f"{label}{sep}{text}" if label else text)

    def diff(self, old: dict, new: dict, path: str):
        if old == new:
            return

        old_branches = _union_branches(old)
        new_branches = _union_branches(new)
        if old_branches is not None and new_branches is not None:
            self._diff_union(old, new, old_branches, new_branches, path)
        else:
            old_summary = _type_summary(old)
            new_summary = _type_summary(new)
            if old_summary != new_summary:
                # The node changed kind; its new contents are not worth itemizing.
                self._emit(path, f"type changed ({old_summary} → {new_summary})")
                return

            self._diff_enum(old, new, path)
            self._diff_const(old, new, path)
            # Key on `type`, not the summary: a union whose branches summarize alike
            # (e.g. anyOf of two untitled objects) has the same summary as a plain node
            # but must not be recursed into as one.
            if (node_type := old.get("type")) == new.get("type"):
                if node_type == "object":
                    self._diff_object(old, new, path)
                elif node_type == "array":
                    self._diff_array(old, new, path)

        self._diff_default(old, new, path)

    def _diff_union(self, old: dict, new: dict, old_branches: list[dict], new_branches: list[dict], path: str):
        old_groups = _group_branches(old_branches)
        new_groups = _group_branches(new_branches)

        titled = any(
            "title" in branch
            for branches in (*old_groups.values(), *new_groups.values())
            for branch in branches
        )
        if titled:
            for name in sorted(new_groups.keys() - old_groups.keys()):
                self._emit(path, f"added variant `{name}`", sep=": ")
            for name in sorted(old_groups.keys() - new_groups.keys()):
                self._emit(path, f"removed variant `{name}`", sep=": ")
        else:
            # A union of unnamed alternatives (typically a nullable wrapper) reads better
            # as a single type change: e.g. (string → string | null).
            old_summary = _type_summary(old)
            new_summary = _type_summary(new)
            if old_summary != new_summary:
                self._emit(path, f"type changed ({old_summary} → {new_summary})")

        for name in sorted(old_groups.keys() & new_groups.keys()):
            old_branches = old_groups[name]
            new_branches = new_groups[name]
            for old_branch, new_branch in zip(old_branches, new_branches):
                branch_path = _join(path, name) if "title" in old_branch or "title" in new_branch else path
                self.diff(old_branch, new_branch, branch_path)
            if titled and len(old_branches) != len(new_branches):
                action = "added" if len(new_branches) > len(old_branches) else "removed"
                for _ in range(abs(len(new_branches) - len(old_branches))):
                    self._emit(path, f"{action} variant `{name}`", sep=": ")

    def _diff_enum(self, old: dict, new: dict, path: str):
        if "enum" not in old and "enum" not in new:
            return
        # Compare values as JSON renderings: hashable, and `0`/`false` stay distinct.
        old_values = {json.dumps(value) for value in old.get("enum", ())}
        new_values = {json.dumps(value) for value in new.get("enum", ())}
        for value in sorted(new_values - old_values):
            self._emit(path, f"added enum value {value}", sep=": ")
        for value in sorted(old_values - new_values):
            self._emit(path, f"removed enum value {value}", sep=": ")

    def _diff_const(self, old: dict, new: dict, path: str):
        old_const = old.get("const", _MISSING)
        new_const = new.get("const", _MISSING)
        if old_const == new_const:
            return
        if old_const is _MISSING:
            self._emit(path, f"value restricted to constant {json.dumps(new_const)}", sep=": ")
        elif new_const is _MISSING:
            self._emit(path, f"constant value restriction removed (was {json.dumps(old_const)})", sep=": ")
        else:
            self._emit(path, f"const value changed ({json.dumps(old_const)} → {json.dumps(new_const)})")

    def _diff_object(self, old: dict, new: dict, path: str):
        old_required = set(old.get("required", ()))
        new_required = set(new.get("required", ()))
        old_props = old.get("properties", {})
        new_props = new.get("properties", {})

        for name in sorted(new_props.keys() - old_props.keys()):
            suffix = " (required)" if name in new_required else ""
            self.lines.append(f"added `{_join(path, name)}`{suffix}")
        for name in sorted(old_props.keys() - new_props.keys()):
            self.lines.append(f"removed `{_join(path, name)}`")
        for name in sorted(old_props.keys() & new_props.keys()):
            field_path = _join(path, name)
            # `required` is compared as a set: real dumps reorder it with identical content.
            if name in new_required and name not in old_required:
                self.lines.append(f"`{field_path}` became required")
            elif name in old_required and name not in new_required:
                self.lines.append(f"`{field_path}` became optional")
            self.diff(old_props[name], new_props[name], field_path)

        old_extra = _map_value_schema(old)
        new_extra = _map_value_schema(new)
        if old_extra is not None and new_extra is not None:
            self.diff(old_extra, new_extra, path + "[*]")
        elif new_extra is not None:
            self._emit(path, "additional properties now allowed", sep=": ")
        elif old_extra is not None:
            self._emit(path, "additional properties no longer allowed", sep=": ")

        old_patterns = old.get("patternProperties", {})
        new_patterns = new.get("patternProperties", {})
        for pattern in sorted(new_patterns.keys() - old_patterns.keys()):
            self._emit(path, f"added properties matching pattern `{pattern}`", sep=": ")
        for pattern in sorted(old_patterns.keys() - new_patterns.keys()):
            self._emit(path, f"removed properties matching pattern `{pattern}`", sep=": ")
        for pattern in sorted(old_patterns.keys() & new_patterns.keys()):
            self.diff(old_patterns[pattern], new_patterns[pattern], path + "[*]")

        if (old_names := old.get("propertyNames")) != (new_names := new.get("propertyNames")):
            self.diff(old_names or {}, new_names or {}, path + "[*:keys]")

    def _diff_array(self, old: dict, new: dict, path: str):
        if "prefixItems" in old:
            # Fixed tuple (only core.download's return in practice). A list ↔ tuple
            # change never reaches here: the type summaries differ ("array" vs "tuple").
            old_members = old["prefixItems"]
            new_members = new["prefixItems"]
            if len(old_members) != len(new_members):
                self._emit(path, f"tuple length changed ({len(old_members)} → {len(new_members)})")
            for i, (old_member, new_member) in enumerate(zip(old_members, new_members)):
                self.diff(old_member, new_member, f"{path}[{i}]")
        else:
            self.diff(old["items"], new["items"], path + "[]")

    def _diff_default(self, old: dict, new: dict, path: str):
        old_default = old.get("default", _MISSING)
        new_default = new.get("default", _MISSING)
        if old_default == new_default:
            return
        if old_default is _MISSING:
            detail = _format_value(new_default)
            self._emit(path, f"default value added ({detail})" if detail else "default value added")
        elif new_default is _MISSING:
            self._emit(path, "default value removed")
        else:
            old_detail = _format_value(old_default)
            new_detail = _format_value(new_default)
            if old_detail and new_detail:
                self._emit(path, f"default value changed ({old_detail} → {new_detail})")
            else:
                self._emit(path, "default value changed")


def _diff_call_parameters(old: dict, new: dict) -> list[str]:
    """Diff the `Call parameters` schemas. Parameters are keyed by title; positions matter."""
    old_params = {param["title"]: (i, param) for i, param in enumerate(old["prefixItems"])}
    new_params = {param["title"]: (i, param) for i, param in enumerate(new["prefixItems"])}
    added = new_params.keys() - old_params.keys()
    removed = old_params.keys() - new_params.keys()

    # A removed and an added parameter occupying the same position is a rename, not an
    # (alarming, wire-incompatible-looking) removal plus addition.
    renames = {}
    added_by_index = {new_params[title][0]: title for title in added}
    for title in sorted(removed):
        if (new_title := added_by_index.get(old_params[title][0])) is not None:
            renames[title] = new_title
    added -= set(renames.values())
    removed -= renames.keys()

    lines = []
    for title in sorted(added):
        kind = "optional" if "default" in new_params[title][1] else "required"
        lines.append(f"added parameter `{title}` ({kind})")
    for title in sorted(removed):
        lines.append(f"removed parameter `{title}`")

    pairs = [(title, title) for title in old_params.keys() & new_params.keys()] + list(renames.items())
    for old_title, new_title in sorted(pairs, key=lambda pair: pair[1]):
        old_index, old_param = old_params[old_title]
        new_index, new_param = new_params[new_title]
        if old_title != new_title:
            lines.append(f"parameter `{old_title}` renamed to `{new_title}`")
        elif old_index != new_index:
            # Positions are 0-based, matching the "Parameter N" headings on method pages.
            lines.append(f"parameter `{new_title}` moved from position {old_index} to {new_index}")

        had_default = "default" in old_param
        has_default = "default" in new_param
        if had_default != has_default:
            lines.append(f"parameter `{new_title}` became {'required' if had_default else 'optional'}")
            # The presence transition says it all; don't also report it as a default change.
            old_param = {key: value for key, value in old_param.items() if key != "default"}
            new_param = {key: value for key, value in new_param.items() if key != "default"}

        differ = _SchemaDiffer(root_path=new_title, root_label=f"parameter `{new_title}`")
        differ.diff(old_param, new_param, new_title)
        lines.extend(differ.lines)

    return lines


def _diff_return_value(old: dict, new: dict) -> list[str]:
    """Diff the `Return value` schemas. Root lines are bare; the renderer labels them."""
    differ = _SchemaDiffer(root_path="", root_label="")
    differ.diff(old, new, "")
    return differ.lines


def compute_schema_diff(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """Compare two method schemas. Returns (call_params_diff, return_value_diff).

    Both lists empty means the schemas differ only cosmetically (or not at all).
    """
    if old == new:
        return [], []

    old_props = old["properties"]
    new_props = new["properties"]
    return (
        _diff_call_parameters(old_props["Call parameters"], new_props["Call parameters"]),
        _diff_return_value(old_props["Return value"], new_props["Return value"]),
    )


def _diff_items(
    previous: typing.Iterable[APIDumpMethod], current: typing.Iterable[APIDumpMethod],
) -> tuple[list[str], list[str], list[SchemaChange]]:
    """Compute added/removed/changed for a list of APIDumpMethod."""
    prev_by_name = {item.name: item for item in previous}
    cur_by_name = {item.name: item for item in current}

    added = sorted(cur_by_name.keys() - prev_by_name.keys())
    removed = sorted(prev_by_name.keys() - cur_by_name.keys())
    changed = []
    for name in sorted(cur_by_name.keys() & prev_by_name.keys()):
        old_schemas = prev_by_name[name].schemas
        new_schemas = cur_by_name[name].schemas
        if old_schemas == new_schemas:
            continue

        call_diff, return_diff = compute_schema_diff(old_schemas, new_schemas)
        if call_diff or return_diff:
            # No lines means the difference is cosmetic-only; the method is omitted.
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
