from pydantic import Field, Secret

from middlewared.api.base import BaseModel
from middlewared.api.base.model import NotRequired
from middlewared.api.base.types.string import SECRET_VALUE


class SecretDefaults(BaseModel):
    required: Secret[str]
    bare: Secret[str] = Field(default="")
    already_wrapped: Secret[str] = Field(default=Secret("keep"))
    not_required: Secret[str] = Field(default=NotRequired)
    plain: str = Field(default="plain")


def test_bare_secret_default_is_wrapped():
    """A concrete default on a `Secret` field is auto-wrapped into a `Secret` instance."""
    default = SecretDefaults.model_fields["bare"].default
    assert isinstance(default, Secret)
    assert default.get_secret_value() == ""


def test_wrapped_secret_default_is_preserved():
    """An already-`Secret` default is left untouched (not double-wrapped)."""
    default = SecretDefaults.model_fields["already_wrapped"].default
    assert isinstance(default, Secret)
    assert default.get_secret_value() == "keep"


def test_required_secret_field_untouched():
    """A required `Secret` field keeps no default."""
    assert SecretDefaults.model_fields["required"].is_required()


def test_not_required_secret_default_untouched():
    """The `NotRequired` sentinel is not wrapped."""
    assert SecretDefaults.model_fields["not_required"].default is NotRequired


def test_plain_field_default_untouched():
    """Non-`Secret` fields are unaffected."""
    assert SecretDefaults.model_fields["plain"].default == "plain"


def test_wrapped_default_redacts_on_serialization():
    """The auto-wrapped default redacts on serialization instead of leaking a bare value."""
    dumped = SecretDefaults(required="r").model_dump()
    assert dumped["bare"] == SECRET_VALUE
    assert SecretDefaults(required="r").model_dump(expose_secrets=True)["bare"] == ""
