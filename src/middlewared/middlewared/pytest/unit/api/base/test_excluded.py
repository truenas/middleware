from pydantic import Field, Secret
import pytest

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NotRequired, query_result
from middlewared.api.base.handler.accept import accept_params, validate_model
from middlewared.service_exception import ValidationErrors


def check_serialization(test_model: type[BaseModel], test_cases: list[tuple[dict, dict]] | list[dict]):
    """
    Args:
        test_model: The model to serialize.
        test_cases: The first dictionary of each test case is the arguments to pass to the model; the second dictionary
            is the expected result of serialization. A test case represented by a single dictionary will expect the
            result of serialization to equal the args.
    """
    for test_case in test_cases:
        args, dump = (test_case, test_case) if isinstance(test_case, dict) else test_case
        result = validate_model(test_model, args)
        assert result == dump, (args, dump, result)


def test_excluded_field():
    class Object(BaseModel):
        id: int
        name: str

    class CreateObject(Object):
        id: Excluded = excluded_field()

    class CreateArgs(BaseModel):
        data: CreateObject

    with pytest.raises(ValidationErrors) as ve:
        accept_params(CreateArgs, [{"id": 1, "name": "Ivan"}])

    assert ve.value.errors[0].attribute == "data.id"
    assert ve.value.errors[0].errmsg == "Extra inputs are not permitted"


def test_not_required():
    class NestedModel(BaseModel):
        a: int = NotRequired

    class ParentModel(BaseModel):
        k: int

    class NotRequiredTestModel(ParentModel):
        b: int
        c: int = 3
        d: int = NotRequired
        e: NestedModel
        f: NestedModel = Field(default_factory=NestedModel)
        # default_factory must be used here
        g: NestedModel = NotRequired
        h: list[NestedModel] = NotRequired
        i_: int = Field(alias="i", default=NotRequired)
        j: Secret[int] = NotRequired
        k: Excluded = excluded_field()

    test_cases = (
        (
            {"b": 2, "e": {}},
            {"b": 2, "c": 3, "e": {}, "f": {}}
        ),
        (
            {"b": 2, "e": {"a": 1}},
            {"b": 2, "c": 3, "e": {"a": 1}, "f": {}}
        ),
        (
            {"b": 2, "c": -3, "e": {}},
            {"b": 2, "c": -3, "e": {}, "f": {}}
        ),
        (
            {"b": 2, "d": 4, "e": {}},
            {"b": 2, "c": 3, "d": 4, "e": {}, "f": {}}
        ),
        (
            {"b": 2, "e": {}, "f": {}},
            {"b": 2, "c": 3, "e": {}, "f": {}}
        ),
        (
            {"b": 2, "e": {}, "f": {"a": 1}},
            {"b": 2, "c": 3, "e": {}, "f": {"a": 1}}
        ),
        (
            {"b": 2, "e": {}, "g": {}},
            {"b": 2, "c": 3, "e": {}, "f": {}, "g": {}}
        ),
        (
            {"b": 2, "e": {}, "g": {"a": 1}},
            {"b": 2, "c": 3, "e": {}, "f": {}, "g": {"a": 1}}
        ),
        (
            {"b": 2, "e": {}, "h": []},
            {"b": 2, "c": 3, "e": {}, "f": {}, "h": []}
        ),
        (
            {"b": 2, "e": {}, "h": [{}]},
            {"b": 2, "c": 3, "e": {}, "f": {}, "h": [{}]}
        ),
        (
            {"b": 2, "e": {}, "h": [{"a": 1}]},
            {"b": 2, "c": 3, "e": {}, "f": {}, "h": [{"a": 1}]}
        ),
        (
            {"b": 2, "e": {}, "h": [{"a": 1}, {}]},
            {"b": 2, "c": 3, "e": {}, "f": {}, "h": [{"a": 1}, {}]}
        ),
        (
            {"b": 2, "e": {}, "i": 4},
            {"b": 2, "c": 3, "e": {}, "f": {}, "i": 4}
        ),
        (
            {"b": 2, "e": {}, "j": 4},
            {"b": 2, "c": 3, "e": {}, "f": {}, "j": 4}
        ),
    )
    check_serialization(NotRequiredTestModel, test_cases)


def test_update_metaclass():
    class NestedModel(BaseModel):
        a: int
    
    class NestedUpdateModel(BaseModel, metaclass=ForUpdateMetaclass):
        y: str

    class UpdateModel(BaseModel, metaclass=ForUpdateMetaclass):
        b: int
        c: NestedModel
        d: NestedUpdateModel

    test_cases = (
        {},
        {"b": 2},
        {"c": {"a": 1}},
        {"d": {}},
        {"d": {"y": ""}},
    )
    check_serialization(UpdateModel, test_cases)


def test_not_required_entry_field():
    class MyEntry(BaseModel):
        x: int = NotRequired

    MyQueryResult = query_result(MyEntry)
    check_serialization(MyQueryResult, [
        {"result": []},
        {"result": {}},
        {"result": {"x": 4}},
    ])


def test_serializers():
    class A(BaseModel):
        a1: int
        a2: int = NotRequired

    class B(A, metaclass=ForUpdateMetaclass):
        b1: A
        b2: str

    class C(B):
        c1: A
        c2: B

    assert A.__class__.__name__ == "_BaseModelMetaclass"
    assert B.__class__ is C.__class__ is ForUpdateMetaclass

    SERIALIZER_NAME = "serializer"  # defined in model.py
    assert getattr(A, SERIALIZER_NAME).__name__ == "_not_required_serializer"
    assert getattr(B, SERIALIZER_NAME).__name__ == getattr(C, SERIALIZER_NAME).__name__ == "_for_update_serializer"

    assert all(len(model.__pydantic_decorators__.model_serializers) == 1 for model in (A, B, C))

    check_serialization(C, [
        {},
        {"c1": {"a1": 1}},
        {"c1": {"a1": 1, "a2": 2}},
        {"c2": {}},
        {"c2": {"b1": {"a1": 1}}},
        {"c2": {"b1": {"a1": 1, "a2": 2}}},
        {"c2": {"b2": "b"}},
        {"c2": {"b1": {"a1": 1}, "b2": "b"}},
        {"c1": {"a1": 1}, "c2": {}},
    ])
