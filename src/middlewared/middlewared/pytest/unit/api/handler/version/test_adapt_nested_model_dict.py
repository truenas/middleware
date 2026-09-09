from typing import Any

import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.pytest.unit.helpers import TestModelProvider


class Contact(BaseModel):
    name: str
    email: str


ContactV1 = Contact


class Settings(BaseModel):
    contacts: dict[str, ContactV1]


SettingsV1 = Settings


class Contact(BaseModel):
    first_name: str
    last_name: str
    email: str

    @classmethod
    def from_previous(cls, value):
        value["first_name"], value["last_name"] = value.pop("name").split(" ", 1)

        return value

    @classmethod
    def to_previous(cls, value):
        value["name"] = f"{value.pop('first_name')} {value.pop('last_name')}"

        return value


ContactV2 = Contact


class Settings(BaseModel):
    contacts: dict[str, ContactV2]


SettingsV2 = Settings


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "version1,value,version2,result",
    [
        (
            "v1",
            {"contacts": {"support": {"name": "Jane Doe", "email": "jane@ixsystems.com"}}},
            "v2",
            {"contacts": {"support": {"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}}},
        ),
        (
            "v2",
            {"contacts": {"support": {"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}}},
            "v1",
            {"contacts": {"support": {"name": "Jane Doe", "email": "jane@ixsystems.com"}}},
        ),
    ],
)
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter(
        [
            APIVersion("v1", TestModelProvider({"Settings": SettingsV1})),
            APIVersion("v2", TestModelProvider({"Settings": SettingsV2})),
        ]
    )

    assert await adapter.adapt(value, "Settings", version1, version2) == result


class Metadata(BaseModel):
    labels: dict[str, str]
    ports: dict[int, str]
    extra: dict[str, Any]


MetadataV1 = Metadata
MetadataV2 = Metadata


def scalar_maps():
    return {
        "labels": {"role": "primary"},
        "ports": {443: "https"},
        # Shaped like a `Contact` payload: an adapter that keyed off the values rather than off the
        # declared value type would try to convert this one.
        "extra": {"owner": {"name": "Jane Doe", "email": "jane@ixsystems.com"}},
    }


@pytest.mark.asyncio
async def test_adapt_scalar_map():
    adapter = APIVersionsAdapter(
        [
            APIVersion("v1", TestModelProvider({"Metadata": MetadataV1})),
            APIVersion("v2", TestModelProvider({"Metadata": MetadataV2})),
        ]
    )

    assert await adapter.adapt(scalar_maps(), "Metadata", "v1", "v2") == scalar_maps()


class Preferences(BaseModel):
    contact: ContactV1 | dict[str, ContactV1]


PreferencesV1 = Preferences


class Preferences(BaseModel):
    contact: ContactV2 | dict[str, ContactV2]


PreferencesV2 = Preferences


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "version1,value,version2,result",
    [
        (
            "v1",
            {"contact": {"name": "Jane Doe", "email": "jane@ixsystems.com"}},
            "v2",
            {"contact": {"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}},
        ),
        (
            "v2",
            {"contact": {"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}},
            "v1",
            {"contact": {"name": "Jane Doe", "email": "jane@ixsystems.com"}},
        ),
    ],
)
async def test_adapt_single_model_wins_over_map(version1, value, version2, result):
    """A lone nested model is still a `dict`, so a field that accepts either shape must adapt it as a model."""
    adapter = APIVersionsAdapter(
        [
            APIVersion("v1", TestModelProvider({"Preferences": PreferencesV1})),
            APIVersion("v2", TestModelProvider({"Preferences": PreferencesV2})),
        ]
    )

    assert await adapter.adapt(value, "Preferences", version1, version2) == result
