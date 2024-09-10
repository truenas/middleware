from unittest.mock import ANY

from pydantic import EmailStr
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.service_exception import ValidationErrors, ValidationError


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


def test_adapt_validation():
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Settings": SettingsV1}),
        APIVersion("v2", {"Settings": SettingsV2}),
    ])
    with pytest.raises(ValidationErrors) as ve:
        assert adapter.adapt({"email": ""}, "Settings", "v1", "v2")

    assert ve.value.errors == [ValidationError("email", ANY)]


def test_adapt_default():
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Settings": SettingsV1}),
        APIVersion("v2", {"Settings": SettingsV2}),
    ])
    assert adapter.adapt({}, "Settings", "v1", "v2") == {"emails": []}
