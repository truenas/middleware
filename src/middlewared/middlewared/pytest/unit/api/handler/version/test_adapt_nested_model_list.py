import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter


class Contact(BaseModel):
    name: str
    email: str


class SettingsV1(BaseModel):
    contacts: list[Contact]


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


class SettingsV2(BaseModel):
    contacts: list[Contact]


@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"contacts": [{"name": "Jane Doe", "email": "jane@ixsystems.com"}]},
     "v2", {"contacts": [{"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}]}),
    ("v2", {"contacts": [{"first_name": "Jane", "last_name": "Doe", "email": "jane@ixsystems.com"}]},
     "v1", {"contacts": [{"name": "Jane Doe", "email": "jane@ixsystems.com"}]}),
])
def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Settings": SettingsV1}),
        APIVersion("v2", {"Settings": SettingsV2}),
    ])

    assert adapter.adapt(value, "Settings", version1, version2) == result
