# -*- coding=utf-8 -*-
"""Unit tests for the cross-version API changelog diff (`changelog.py`)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import changelog as cl


# --- builders for the canonical `--dump-api` schema shape ------------------------------


def method_schemas(call_params=None, return_value=None):
    """A method schema as it appears in the dump: object with Call parameters + Return value."""
    return {
        "type": "object",
        "properties": {
            "Call parameters": {
                "type": "array",
                "prefixItems": list(call_params or []),
                "items": False,
            },
            "Return value": {} if return_value is None else return_value,
        },
    }


def param(title, **extra):
    """A single positional call parameter (every parameter has a unique title)."""
    return {"title": title, "type": "string", **extra}


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


def call_diff(old_params, new_params):
    return cl.compute_schema_diff(
        method_schemas(call_params=old_params), method_schemas(call_params=new_params)
    )[0]


def return_diff(old_rv, new_rv):
    return cl.compute_schema_diff(
        method_schemas(return_value=old_rv), method_schemas(return_value=new_rv)
    )[1]


# --- whole-schema short-circuits -------------------------------------------------------


def test_identical_schemas_produce_no_diff():
    schema = method_schemas([param("x")], obj({"a": {"type": "string"}}))
    assert cl.compute_schema_diff(schema, schema) == ([], [])


def test_cosmetic_only_change_is_ignored():
    # Description/title wording is never read, so it is not a reportable change.
    old = method_schemas(return_value={"type": "string", "description": "old words"})
    new = method_schemas(return_value={"type": "string", "description": "new words"})
    assert cl.compute_schema_diff(old, new) == ([], [])


# --- call parameters -------------------------------------------------------------------

CALL_PARAM_CASES = [
    pytest.param(
        [param("a")],
        [param("a"), param("b")],
        ["added parameter `b` (required)"],
        id="added-required-param",
    ),
    pytest.param(
        [param("a")],
        [param("a"), param("b", default="x")],
        ["added parameter `b` (optional)"],
        id="added-optional-param",
    ),
    pytest.param(
        [param("a"), param("b")],
        [param("a")],
        ["removed parameter `b`"],
        id="removed-param",
    ),
    pytest.param(
        [param("old_name")],
        [param("new_name")],
        ["parameter `old_name` renamed to `new_name`"],
        id="same-position-rename",
    ),
    pytest.param(
        [param("a"), param("b")],
        [param("b"), param("a")],
        [
            "parameter `a` moved from position 0 to 1",
            "parameter `b` moved from position 1 to 0",
        ],
        id="position-move",
    ),
    pytest.param(
        [param("a", default="x")],
        [param("a")],
        ["parameter `a` became required"],
        id="param-became-required-suppresses-default-removed",
    ),
    pytest.param(
        [param("a")],
        [param("a", default="x")],
        ["parameter `a` became optional"],
        id="param-became-optional-suppresses-default-added",
    ),
    pytest.param(
        [param("a", type="string")],
        [param("a", type="integer")],
        ["parameter `a` type changed (string → integer)"],
        id="param-type-change",
    ),
]


@pytest.mark.parametrize("old_params,new_params,expected", CALL_PARAM_CASES)
def test_call_parameter_diff(old_params, new_params, expected):
    assert call_diff(old_params, new_params) == expected


# --- return value: objects, fields, transitions ----------------------------------------

RETURN_VALUE_CASES = [
    pytest.param(
        obj({"a": {"type": "string"}}),
        obj({"a": {"type": "string"}, "b": {"type": "string"}}, required=["b"]),
        ["added `b` (required)"],
        id="added-required-field",
    ),
    pytest.param(
        obj({"a": {"type": "string"}, "b": {"type": "string"}}),
        obj({"a": {"type": "string"}}),
        ["removed `b`"],
        id="removed-field",
    ),
    pytest.param(
        obj({"a": {"type": "string", "default": "x"}}),
        obj({"a": {"type": "string"}}, required=["a"]),
        ["`a` became required"],
        id="field-became-required-suppresses-default-removed",
    ),
    pytest.param(
        obj({"a": {"type": "string"}}, required=["a"]),
        obj({"a": {"type": "string", "default": "x"}}),
        ["`a` became optional"],
        id="field-became-optional-suppresses-default-added",
    ),
    pytest.param(
        obj({"a": {"type": "string"}, "b": {"type": "string"}}, required=["a", "b"]),
        obj({"a": {"type": "string"}, "b": {"type": "string"}}, required=["b", "a"]),
        [],
        id="required-reordering-is-not-a-change",
    ),
    pytest.param(
        {"type": "string"},
        {"type": "integer"},
        ["type changed (string → integer)"],
        id="root-type-change",
    ),
    pytest.param(
        {"type": "string"},
        {"anyOf": [{"type": "string"}, {"type": "null"}]},
        ["type changed (string → string | null)"],
        id="became-nullable",
    ),
    pytest.param(
        {"enum": ["a", "b"]},
        {"enum": ["b", "c"]},
        ['added enum value "c"', 'removed enum value "a"'],
        id="enum-values",
    ),
    pytest.param(
        obj({"a": {"type": "string"}}),
        obj({"a": {"type": "string", "const": "x"}}),
        ['`a`: value restricted to constant "x"'],
        id="const-added",
    ),
    pytest.param(
        obj({"a": {"type": "integer", "default": 1}}),
        obj({"a": {"type": "integer", "default": 2}}),
        ["`a` default value changed (1 → 2)"],
        id="default-changed",
    ),
    pytest.param(
        obj({"a": {"type": "integer"}}),
        obj({"a": {"type": "integer", "default": 5}}),
        ["`a` default value added (5)"],
        id="default-added",
    ),
    pytest.param(
        obj({"a": {"type": "array", "items": {"type": "string"}}}),
        obj({"a": {"type": "array", "items": {"type": "integer"}}}),
        ["`a[]` type changed (string → integer)"],
        id="array-item-type-change",
    ),
    pytest.param(
        {"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer"}]},
        {
            "type": "array",
            "prefixItems": [
                {"type": "string"},
                {"type": "integer"},
                {"type": "boolean"},
            ],
        },
        ["tuple length changed (2 → 3)"],
        id="tuple-length-change",
    ),
    pytest.param(
        {"type": "object", "properties": {}},
        {"type": "object", "properties": {}, "additionalProperties": False},
        ["additional properties no longer allowed"],
        id="additional-properties-disallowed",
    ),
    pytest.param(
        {"type": "object", "properties": {}, "additionalProperties": True},
        {"type": "object", "properties": {}},
        [],
        id="additional-properties-true-equals-absent",
    ),
]


@pytest.mark.parametrize("old_rv,new_rv,expected", RETURN_VALUE_CASES)
def test_return_value_diff(old_rv, new_rv, expected):
    assert return_diff(old_rv, new_rv) == expected


# --- unions ----------------------------------------------------------------------------


def test_titled_union_added_and_removed_variant():
    old = {
        "anyOf": [
            obj({"a": {"type": "string"}}) | {"title": "A"},
            obj({"b": {"type": "string"}}) | {"title": "B"},
        ]
    }
    new = {
        "anyOf": [
            obj({"a": {"type": "string"}}) | {"title": "A"},
            obj({"c": {"type": "string"}}) | {"title": "C"},
        ]
    }
    assert return_diff(old, new) == ["added variant `C`", "removed variant `B`"]


def test_anyof_and_oneof_are_interchangeable():
    branches = [
        obj({"a": {"type": "string"}}) | {"title": "A"},
        obj({"b": {"type": "string"}}) | {"title": "B"},
    ]
    assert return_diff({"anyOf": branches}, {"oneOf": list(branches)}) == []


def test_union_recurses_into_same_named_branch():
    old = {"anyOf": [obj({"a": {"type": "string"}}) | {"title": "A"}]}
    new = {"anyOf": [obj({"a": {"type": "integer"}}) | {"title": "A"}]}
    assert return_diff(old, new) == ["`A.a` type changed (string → integer)"]


# --- nested dot-notation paths ---------------------------------------------------------


def test_nested_field_path_uses_dot_notation():
    old = obj({"outer": obj({"inner": {"type": "string"}})})
    new = obj({"outer": obj({"inner": {"type": "integer"}})})
    assert return_diff(old, new) == ["`outer.inner` type changed (string → integer)"]


# --- compute_changelog over method lists (stubbed APIDump) -----------------------------


class _Method:
    def __init__(self, name, schemas):
        self.name = name
        self.schemas = schemas


class _Dump:
    def __init__(self, version, methods):
        self.version = version
        self.methods = methods


def test_compute_changelog_partitions_methods():
    unchanged = method_schemas([param("x")])
    old = _Dump(
        "25.10.0",
        [
            _Method("svc.kept", unchanged),
            _Method("svc.gone", method_schemas([param("x")])),
            _Method("svc.touched", method_schemas([param("x")])),
        ],
    )
    new = _Dump(
        "26.0.0",
        [
            _Method("svc.kept", unchanged),
            _Method("svc.fresh", method_schemas([param("x")])),
            _Method("svc.touched", method_schemas([param("x"), param("y")])),
        ],
    )

    log = cl.compute_changelog(old, new)  # type: ignore[arg-type]

    assert log.old_version == "25.10.0"
    assert log.methods_added == ["svc.fresh"]
    assert log.methods_removed == ["svc.gone"]
    assert [c.name for c in log.methods_changed] == ["svc.touched"]
    assert log.methods_changed[0].call_params_diff == ["added parameter `y` (required)"]
    assert log.methods_changed[0].return_value_diff == []
    assert not log.is_empty()


def test_compute_changelog_empty_when_nothing_changed():
    methods = [_Method("svc.kept", method_schemas([param("x")]))]
    log = cl.compute_changelog(_Dump("a", methods), _Dump("b", list(methods)))  # type: ignore[arg-type]
    assert log.is_empty()
