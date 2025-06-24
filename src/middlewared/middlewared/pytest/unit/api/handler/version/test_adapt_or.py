import copy

import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.pytest.unit.helpers import TestModelProvider


class AdvancedPerms(BaseModel):
    READ: bool = False
    WRITE: bool = False


class BasicPerms(BaseModel):
    BASIC: bool = False


class Entry(BaseModel):
    perms: AdvancedPerms | BasicPerms


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [
    {"perms": {"BASIC": True}},
    {"perms": {"READ": True, "WRITE": True}},
])
async def test_adapt(value):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({
            "Entry": Entry,
        })),
        APIVersion("v2", TestModelProvider({
            "Entry": Entry,
        })),
    ])
    assert await adapter.adapt(copy.deepcopy(value), "Entry", "v1", "v2") == value
