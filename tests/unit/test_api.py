from pydantic import Field, Secret

from middlewared.api.base import BaseModel, NotRequired
from middlewared.api.base.handler.result import serialize_result


def test_dump_by_alias():
    class AliasModel(BaseModel):
        field1_: int = Field(..., alias='field1')
        field2: str
        field3_: bool = Field(alias='field3', default=False)

    class AliasModelResult(BaseModel):
        result: AliasModel

    result = {'field1': 1, 'field2': 'two'}
    dump = serialize_result(AliasModelResult, result, False)

    assert dump == {'field1': 1, 'field2': 'two', 'field3': False}


def test_not_required():
    class NestedModel(BaseModel):
        a: int = NotRequired

    class NotRequiredModel(BaseModel):
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
            # args passed to NotRequiredModel
            {"b": 2, "c": 3, "e": {}, "f": {}}
            # expected result for model_dump
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
    for args, dump in test_cases:
        result = NotRequiredModel(**args).model_dump(context={"expose_secrets": True}, warnings=False, by_alias=True)
        assert result == dump, (args, dump, result)
