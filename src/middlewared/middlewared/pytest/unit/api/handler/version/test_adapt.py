from pydantic import EmailStr
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter

from .utils import TestModelProvider


class SettingsV1(BaseModel):
    email: EmailStr | None = None


class SettingsV2(BaseModel):
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


class SettingsV3(BaseModel):
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


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v1", {"email": "alice@ixsystems.com"}, "v3", {"contacts": [{"name": "Alice", "email": "alice@ixsystems.com"}]}),
    ("v3", {"contacts": [{"name": "Alice", "email": "alice@ixsystems.com"}]}, "v1", {"email": "alice@ixsystems.com"}),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({"Settings": SettingsV1})),
        APIVersion("v2", TestModelProvider({"Settings": SettingsV2})),
        APIVersion("v3", TestModelProvider({"Settings": SettingsV3})),
    ])
    assert await adapter.adapt(value, "Settings", version1, version2) == result
