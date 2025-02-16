import pytest
from unittest.mock import Mock

from middlewared.api.base import BaseModel
from middlewared.api.base.decorator import api_method
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.base.server.legacy_api_method import LegacyAPIMethod
from middlewared.pytest.unit.helpers import TestModelProvider


class MethodArgs(BaseModel):
    number: int
    multiplier: int = 2


class MethodResult(BaseModel):
    result: str


MethodArgsV1 = MethodArgs
MethodResultV1 = MethodResult


class MethodArgs(BaseModel):
    number: int
    text: str = "Default"
    multiplier: int = 2


class MethodResult(BaseModel):
    result: int

    @classmethod
    def to_previous(cls, value):
        value["result"] = str(value["result"])

        return value


@api_method(MethodArgs, MethodResult, private=True)
def method(number, text, multiplier):
    return {
        "number": number * multiplier,
        "text": text * multiplier,
    }


adapter = APIVersionsAdapter([
    APIVersion("v1", TestModelProvider({"MethodArgs": MethodArgsV1, "MethodResult": MethodResultV1})),
    APIVersion("v2", TestModelProvider({"MethodArgs": MethodArgs, "MethodResult": MethodResult})),
])
legacy_api_method = LegacyAPIMethod(
    Mock(
        get_method=Mock(return_value=(Mock(), method))
    ),
    "core.test",
    "v1",
    adapter,
)


@pytest.mark.asyncio
async def test_adapt_params():
    assert await legacy_api_method._adapt_params([1]) == [1, "Default", 2]
