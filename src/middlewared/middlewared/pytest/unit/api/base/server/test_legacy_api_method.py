from unittest.mock import Mock

from middlewared.api.base import BaseModel
from middlewared.api.base.decorator import api_method
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.base.server.legacy_api_method import LegacyAPIMethod


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


@api_method(MethodArgs, MethodResult)
def method(number, text, multiplier):
    return {
        "number": number * multiplier,
        "text": text * multiplier,
    }


adapter = APIVersionsAdapter([
    APIVersion("v1", {"MethodArgs": MethodArgsV1, "MethodResult": MethodResultV1}),
    APIVersion("v2", {"MethodArgs": MethodArgs, "MethodResult": MethodResult}),
])
legacy_api_method = LegacyAPIMethod(
    Mock(
        get_method=Mock(return_value=(Mock(), method))
    ),
    "core.test",
    "v1",
    adapter,
)


def test_adapt_params():
    assert legacy_api_method._adapt_params([1]) == [1, "Default", 2]


def test_adapt_result():
    assert legacy_api_method._adapt_result(1) == "1"
