from pydantic import EmailStr
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter


class Settings(BaseModel):
    email: EmailStr | None = None


class UpdateSettingsArgsV1(BaseModel):
    settings: Settings


class Settings(BaseModel):
    emails: list[EmailStr]

    @classmethod
    def from_previous(cls, value):
        email = value.pop("email")

        if email is None:
            value["emails"] = []
        else:
            value["emails"] = [email]

        return value

    @classmethod
    def to_previous(cls, value):
        emails = value.pop("emails")

        if emails:
            value["email"] = emails[0]
        else:
            value["email"] = None

        return value


class UpdateSettingsArgsV2(BaseModel):
    settings: Settings


class Settings(BaseModel):
    contacts: list[dict]

    @classmethod
    def from_previous(cls, value):
        emails = value.pop("emails")

        value["contacts"] = [{"name": email.split("@")[0].title(), "email": email}
                             for email in emails]

        return value

    @classmethod
    def to_previous(cls, value):
        contacts = value.pop("contacts")

        value["emails"] = [contact["email"] for contact in contacts]

        return value


class UpdateSettingsArgsV3(BaseModel):
    settings: Settings


@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"settings": {"email": "alice@ixsystems.com"}},
     "v3", {"settings": {"contacts": [{"name": "Alice", "email": "alice@ixsystems.com"}]}}),
    ("v3", {"settings": {"contacts": [{"name": "Alice", "email": "alice@ixsystems.com"}]}},
     "v1", {"settings": {"email": "alice@ixsystems.com"}}),
])
def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"UpdateSettingsArgs": UpdateSettingsArgsV1}),
        APIVersion("v2", {"UpdateSettingsArgs": UpdateSettingsArgsV2}),
        APIVersion("v3", {"UpdateSettingsArgs": UpdateSettingsArgsV3}),
    ])

    assert adapter.adapt(value, "UpdateSettingsArgs", version1, version2) == result
