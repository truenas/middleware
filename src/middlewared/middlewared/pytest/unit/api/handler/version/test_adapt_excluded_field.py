import pytest

from middlewared.api.base import BaseModel, Excluded, excluded_field
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class EntryModelV1(BaseModel):
    id: int
    name: str


class CreateModelV1(EntryModelV1):
    id: Excluded = excluded_field()


class EntryModelV2(BaseModel):
    id: int
    name: str


class CreateModelV2(EntryModelV2):
    id: Excluded = excluded_field()


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"name": "ivan"}, "v2", {"name": "ivan"}),
    ("v2", {"name": "ivan"}, "v1", {"name": "ivan"}),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Create": CreateModelV1})),
        APIVersion("v2", TestModelProvider({"Create": CreateModelV2})),
    ])
    assert await adapter.adapt(value, "Create", version1, version2) == result
