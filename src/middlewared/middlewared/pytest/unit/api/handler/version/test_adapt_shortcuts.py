import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_args, single_argument_result
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class ModelV1(BaseModel, metaclass=ForUpdateMetaclass):
    number: int = 1


class ModelV2(BaseModel, metaclass=ForUpdateMetaclass):
    number: int = 1
    text: str = "1"


@pytest.mark.asyncio
async def test_adapt_for_update_metaclass():
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Model": ModelV1})),
        APIVersion("v2", TestModelProvider({"Model": ModelV2})),
    ])
    assert await adapter.adapt({}, "Model", "v1", "v2") == {}


class ArgsV1(BaseModel):
    count: int
    force: bool = False


@single_argument_args("options")
class ArgsV2(BaseModel):
    count: int
    exclude: list[str] = []
    force: bool = False

    @classmethod
    def from_previous(cls, value):
        return {
            "options": value,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"count": 1}, "v2", {"options": {"count": 1, "force": False}}),
])
async def test_adapt_single_argument_args(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Args": ArgsV1})),
        APIVersion("v2", TestModelProvider({"Args": ArgsV2})),
    ])
    assert await adapter.adapt(value, "Args", version1, version2) == result


class ResultV1(BaseModel):
    result: int


@single_argument_result
class ResultV2(BaseModel):
    value: int
    status: str

    @classmethod
    def from_previous(cls, value):
        return {
            "result": {
                "value": value["result"],
                "status": "OK",
            },
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"result": 1}, "v2", {"result": {"value": 1, "status": "OK"}}),
])
async def test_adapt_single_argument_result(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Result": ResultV1})),
        APIVersion("v2", TestModelProvider({"Result": ResultV2})),
    ])
    assert await adapter.adapt(value, "Result", version1, version2) == result
