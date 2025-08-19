from pydantic import Field
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class SettingsV1(BaseModel):
    text1: str
    field_with_alias: str = Field(alias="alias", default="field_with_alias")
    field_with_factory: str = Field(alias="other-alias", default_factory=lambda: "field_with_factory")


class SettingsV2(SettingsV1):
    text2: str = "text2"


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    (
        "v1",
        {"text1": "text1"},
        "v2",
        {"text1": "text1", "text2": "text2", "alias": "field_with_alias", "other-alias": "field_with_factory"},
    ),
    (
        "v2",
        {"text1": "text1", "text2": "text2"},
        "v1",
        {"text1": "text1", "alias": "field_with_alias", "other-alias": "field_with_factory"},
    ),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Settings": SettingsV1})),
        APIVersion("v2", TestModelProvider({"Settings": SettingsV2})),
    ])
    assert await adapter.adapt(value, "Settings", version1, version2) == result
