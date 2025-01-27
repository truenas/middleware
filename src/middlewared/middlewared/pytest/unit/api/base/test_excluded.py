from pydantic import Field, Secret
import pytest

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NotRequired, NotRequiredModel
from middlewared.api.base.handler.accept import accept_params, validate_model
from middlewared.service_exception import ValidationErrors


class Object(BaseModel):
    id: int
    name: str


class CreateObject(Object):
    id: Excluded = excluded_field()


class CreateArgs(BaseModel):
    data: CreateObject


def check_serialization(test_model, test_cases):
    for args, dump in test_cases:
        result = validate_model(test_model, args)
        assert result == dump, (args, dump, result)


def test_excluded_field():
    with pytest.raises(ValidationErrors) as ve:
        accept_params(CreateArgs, [{"id": 1, "name": "Ivan"}])

    assert ve.value.errors[0].attribute == "data.id"
    assert ve.value.errors[0].errmsg == "Extra inputs are not permitted"


def test_not_required():
    class NestedModel(NotRequiredModel):
        a: int = NotRequired

    class NotRequiredTestModel(NotRequiredModel):
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

    class UpdateModel(BaseModel, metaclass=ForUpdateMetaclass):
        b: int
        c: NestedModel

    test_cases = (
        (
            {}, {}
        ),
        (
            {"b": 2}, {"b": 2}
        ),
        (
            {"c": {"a": 1}}, {"c": {"a": 1}}
        ),
    )
    check_serialization(UpdateModel, test_cases)
