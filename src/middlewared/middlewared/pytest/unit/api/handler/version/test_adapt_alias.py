from pydantic import Field
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class SettingsV1(BaseModel):
    query_options: str = Field(alias="query-options", default="canary")


class SettingsV2(BaseModel):
    query_options: str = Field(alias="query-options", default="canary")


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"query-options": "options"}, "v2", {"query-options": "options"}),
    ("v2", {"query-options": "options"}, "v1", {"query-options": "options"}),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Settings": SettingsV1})),
        APIVersion("v2", TestModelProvider({"Settings": SettingsV2})),
    ])
    assert await adapter.adapt(value, "Settings", version1, version2) == result
