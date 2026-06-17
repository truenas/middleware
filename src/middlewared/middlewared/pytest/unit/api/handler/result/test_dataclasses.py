from dataclasses import dataclass

from middlewared.api.base.handler.result import serialize_nonmodel_result


@dataclass(slots=True, kw_only=True)
class Inner:
    a: int
    b: str | None


@dataclass(slots=True, kw_only=True)
class Outer:
    name: str
    tags: list[str]
    inner: Inner


def test_single_dataclass_becomes_dict():
    result = serialize_nonmodel_result(Inner(a=1, b="x"))
    assert result == {"a": 1, "b": "x"}
    assert isinstance(result, dict)


def test_list_of_dataclasses():
    result = serialize_nonmodel_result([Inner(a=1, b=None), Inner(a=2, b="y")])
    assert result == [{"a": 1, "b": None}, {"a": 2, "b": "y"}]


def test_nested_dataclass_is_recursive():
    result = serialize_nonmodel_result(Outer(name="n", tags=["t1"], inner=Inner(a=5, b="z")))
    assert result == {"name": "n", "tags": ["t1"], "inner": {"a": 5, "b": "z"}}


def test_dataclasses_nested_in_dict_and_list():
    result = serialize_nonmodel_result({"items": [Inner(a=1, b="x")], "count": 1})
    assert result == {"items": [{"a": 1, "b": "x"}], "count": 1}


def test_plain_result_passes_through_unchanged():
    value = {"data": {"id": [1, 2, 3], "name": "x"}, "flag": True, "n": None}
    assert serialize_nonmodel_result(value) == value
    # non-dataclass scalars are returned as-is
    assert serialize_nonmodel_result("string") == "string"
    assert serialize_nonmodel_result(42) == 42


def test_dataclass_type_is_not_converted():
    # a dataclass *class* (not an instance) must pass through untouched
    assert serialize_nonmodel_result(Inner) is Inner
