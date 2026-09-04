from pydantic import ConfigDict
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class EntryV1Strict(BaseModel):
    name: str


class EntryV1Extra(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str


class EntryV2(BaseModel):
    name: str
    tier: str | None = None


class ArgV1(BaseModel):
    name: str
    legacy_opt: bool = False


class ArgV2Strict(BaseModel):
    name: str


class ArgV2Extra(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "v1_model,result",
    [
        (EntryV1Extra, {"name": "tank", "tier": "PERFORMANCE"}),
        (EntryV1Strict, {"name": "tank"}),
    ],
)
async def test_downgrade_field_missing_from_target(v1_model, result):
    """A field declared only in the newer model survives downgrade if the older model accepts extra fields."""
    adapter = APIVersionsAdapter(
        [
            APIVersion("v1", TestModelProvider({"Entry": v1_model})),
            APIVersion("v2", TestModelProvider({"Entry": EntryV2})),
        ]
    )
    assert await adapter.adapt({"name": "tank", "tier": "PERFORMANCE"}, "Entry", "v2", "v1") == result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "v2_model,result",
    [
        (ArgV2Extra, {"name": "eth0", "legacy_opt": True}),
        (ArgV2Strict, {"name": "eth0"}),
    ],
)
async def test_upgrade_field_missing_from_target(v2_model, result):
    """A field declared only in the older model survives upgrade if the newer model accepts extra fields."""
    adapter = APIVersionsAdapter(
        [
            APIVersion("v1", TestModelProvider({"Arg": ArgV1})),
            APIVersion("v2", TestModelProvider({"Arg": v2_model})),
        ]
    )
    assert await adapter.adapt({"name": "eth0", "legacy_opt": True}, "Arg", "v1", "v2") == result
