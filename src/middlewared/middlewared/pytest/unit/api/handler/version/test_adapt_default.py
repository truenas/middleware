import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class SettingsV1(BaseModel):
    text1: str


class SettingsV2(BaseModel):
    text1: str
    text2: str = "text2"


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"text1": "text1"}, "v2", {"text1": "text1", "text2": "text2"}),
    ("v2", {"text1": "text1", "text2": "text2"}, "v1", {"text1": "text1"}),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Settings": SettingsV1})),
        APIVersion("v2", TestModelProvider({"Settings": SettingsV2})),
    ])
    assert await adapter.adapt(value, "Settings", version1, version2) == result
