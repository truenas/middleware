import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.pytest.unit.helpers import TestModelProvider


class Contact(BaseModel):
    name: str
    email: str


ContactV1 = Contact


class Settings(BaseModel):
    contacts: list[ContactV1]


SettingsV1 = Settings


class Contact(BaseModel):
    first_name: str
    last_name: str
    email: str

    @classmethod
    def from_previous(cls, value):
        if " " in value["name"]:
            value["first_name"], value["last_name"] = value.pop("name").split(" ", 1)
        else:
            value["first_name"] = value.pop("name")
            value["last_name"] = ""

        return value

    @classmethod
    def to_previous(cls, value):
        value["name"] = f"{value.pop('first_name')} {value.pop('last_name')}"

        return value


ContactV2 = Contact


class Settings(BaseModel):
    contacts: list[ContactV2]


SettingsV2 = Settings


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"contacts": [{"name": "Jane Doe", "email": "jane@ixsystems.com"}]},
     "v2", {"contacts": [{"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}]}),
    ("v2", {"contacts": [{"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}]},
     "v1", {"contacts": [{"name": "Jane Doe", "email": "jane@ixsystems.com"}]}),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Settings": SettingsV1})),
        APIVersion("v2", TestModelProvider({"Settings": SettingsV2})),
    ])

    assert await adapter.adapt(value, "Settings", version1, version2) == result
