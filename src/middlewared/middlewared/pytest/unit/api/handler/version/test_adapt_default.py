import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter


class SettingsV1(BaseModel):
    text1: str


class SettingsV2(BaseModel):
    text1: str
    text2: str = "text2"


@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"text1": "text1"}, "v2", {"text1": "text1", "text2": "text2"}),
    ("v2", {"text1": "text1", "text2": "text2"}, "v1", {"text1": "text1"}),
])
def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Settings": SettingsV1}),
        APIVersion("v2", {"Settings": SettingsV2}),
    ])
    assert adapter.adapt(value, "Settings", version1, version2) == result
