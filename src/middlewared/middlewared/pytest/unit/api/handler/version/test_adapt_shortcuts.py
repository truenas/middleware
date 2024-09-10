import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_args, single_argument_result
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter


class ModelV1(BaseModel, metaclass=ForUpdateMetaclass):
    number: int = 1


class ModelV2(BaseModel, metaclass=ForUpdateMetaclass):
    number: int = 1
    text: str = "1"


def test_adapt_for_update_metaclass():
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Model": ModelV1}),
        APIVersion("v2", {"Model": ModelV2}),
    ])
    assert adapter.adapt({}, "Model", "v1", "v2") == {}


class ArgsV1(BaseModel):
    count: int
    force: bool = False


@single_argument_args("options")
class ArgsV2(BaseModel):
    count: int
    exclude: list[str] = []
    force: bool = False

    def from_previous(cls, value):
        return {
            "options": value,
        }


@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"count": 1}, "v2", {"options": {"count": 1, "force": False}}),
])
def test_adapt_single_argument_args(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Args": ArgsV1}),
        APIVersion("v2", {"Args": ArgsV2}),
    ])
    assert adapter.adapt(value, "Args", version1, version2) == result


class ResultV1(BaseModel):
    result: int


@single_argument_result
class ResultV2(BaseModel):
    value: int
    status: str

    def from_previous(cls, value):
        return {
            "result": {
                "value": value["result"],
                "status": "OK",
            },
        }


@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"result": 1}, "v2", {"result": {"value": 1, "status": "OK"}}),
])
def test_adapt_single_argument_result(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Result": ResultV1}),
        APIVersion("v2", {"Result": ResultV2}),
    ])
    assert adapter.adapt(value, "Result", version1, version2) == result
