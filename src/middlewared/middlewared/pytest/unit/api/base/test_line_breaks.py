from typing import Annotated, Any

from annotated_types import MaxLen
from pydantic import Field, Secret, StringConstraints, ValidationError, create_model
import pytest

from middlewared.api.base import (
    BaseModel,
    ForUpdateMetaclass,
    LongNonEmptyString,
    LongString,
    Multiline,
    NonEmptyString,
    NotRequired,
    Private,
)
from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.handler.full_admin import full_admin_payload_fields
from middlewared.api.base.line_breaks import add_line_break_validators
from middlewared.api.v28_0_0.ups import UPSEntry, UPSUpdate, UPSUpdateArgs
from middlewared.service_exception import ValidationErrors

BREAKS = ("\n", "\r", "\r\n")
MESSAGE = "Line breaks are not allowed"

# Every UPS field that a template interpolates bare into `ups.conf`, `upsd.users` or `upsmon.conf`. A
# line break in one lets the caller append directives of their own -- including the `SHUTDOWNCMD` that
# `UPSEntry.shutdowncmd` is marked `FullAdmin` to protect.
UPS_SINGLE_LINE_FIELDS = ("description", "driver", "identifier", "monpwd", "monuser", "port", "remotehost")


class Checked(BaseModel):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: Any) -> Any:
        return add_line_break_validators(handler(source))


class Nested(Checked):
    inner: str = Field(default="")


class Relaxed(BaseModel):
    """A model that opts out the way `middlewared.plugins.apps.pydantic_utils.BaseModel` does."""

    anything: str = Field(default="")

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: Any) -> Any:
        return handler(source)


class Everything(Checked):
    plain: str = Field(default="")
    long: LongString = Field(default="")
    constrained: Annotated[str, StringConstraints(pattern=r'^[^"]*$')] = Field(default="")
    optional: str | None = Field(default=None)
    union: str | int = Field(default=0)
    in_list: list[str] = Field(default_factory=list)
    in_tuple: tuple[str, int] = Field(default=("", 0))
    in_dict: dict[str, str] = Field(default_factory=dict)
    in_nested_list: dict[str, list[str]] = Field(default_factory=dict)
    secret: Secret[str] = Field(default="")
    private: Private[str] = Field(default="")
    nested: Nested = Field(default_factory=Nested)
    relaxed: Relaxed = Field(default_factory=Relaxed)
    not_required: str = Field(default=NotRequired)


class Marked(Checked):
    marked: Multiline[str] = Field(default="")
    non_empty: Multiline[NonEmptyString] = Field(default="x")
    long: Multiline[LongString] = Field(default="")
    long_non_empty: Multiline[LongNonEmptyString] = Field(default="x")
    constrained: Multiline[Annotated[str, MaxLen(32)]] = Field(default="")
    optional: Multiline[str] | None = Field(default=None)
    in_list: list[Multiline[str]] = Field(default_factory=list)
    in_dict: dict[str, Multiline[str]] = Field(default_factory=dict)
    secret: Secret[Multiline[str]] = Field(default="")
    not_required: Multiline[str] = Field(default=NotRequired)


class MarkedForUpdate(Marked, metaclass=ForUpdateMetaclass):
    pass


def positions(break_: str) -> list[tuple[str, dict[str, Any], tuple[Any, ...]]]:
    """Every shape a string can take in a model, and where pydantic must report a break in it."""
    value = f"before{break_}after"
    return [
        ("plain", {"plain": value}, ("plain",)),
        ("long", {"long": value}, ("long",)),
        ("constrained", {"constrained": value}, ("constrained",)),
        ("optional", {"optional": value}, ("optional",)),
        ("list item", {"in_list": ["ok", value]}, ("in_list", 1)),
        ("tuple member", {"in_tuple": (value, 1)}, ("in_tuple", 0)),
        ("dict value", {"in_dict": {"key": value}}, ("in_dict", "key")),
        ("dict key", {"in_dict": {value: "ok"}}, ("in_dict", value, "[key]")),
        ("item of a nested list", {"in_nested_list": {"key": [value]}}, ("in_nested_list", "key", 0)),
        ("nested model field", {"nested": {"inner": value}}, ("nested", "inner")),
    ]


class TestRejection:
    @pytest.mark.parametrize("break_", BREAKS)
    @pytest.mark.parametrize("label", [name for name, _, _ in positions("\n")])
    def test_a_break_is_rejected_wherever_the_string_is(self, break_, label):
        """A line break in a value nested anywhere is as dangerous as one in a top-level field."""
        payload, loc = next((p, location) for name, p, location in positions(break_) if name == label)
        with pytest.raises(ValidationError) as exc:
            Everything(**payload)

        errors = exc.value.errors()
        assert [error["loc"] for error in errors] == [loc], errors
        assert errors[0]["msg"] == f"Value error, {MESSAGE}"

    @pytest.mark.parametrize("break_", BREAKS)
    def test_a_break_inside_a_secret_is_rejected(self, break_):
        """The value reaching a validator of a `Secret` field is wrapped, so it has to be unwrapped first."""
        with pytest.raises(ValidationError, match=MESSAGE):
            Everything(secret=f"a{break_}b")

    @pytest.mark.parametrize("break_", BREAKS)
    def test_a_break_in_a_private_field_is_rejected(self, break_):
        with pytest.raises(ValidationError, match=MESSAGE):
            Everything(private=f"a{break_}b")

    def test_a_break_in_a_not_required_field_is_rejected(self):
        """A `NotRequired` default makes the field a union, so pydantic reports one error per member."""
        with pytest.raises(ValidationError, match=MESSAGE):
            Everything(not_required="a\nb")

    def test_the_handler_reports_the_position_of_the_string(self):
        """`accept_params` turns the location pydantic reports into the attribute of the validation error."""
        with pytest.raises(ValidationErrors) as exc:
            validate_model(Everything, {"in_list": ["ok", "a\nb"]})

        assert [(error.attribute, error.errmsg) for error in exc.value.errors] == [
            ("in_list.1", f"Value error, {MESSAGE}")
        ]

    def test_the_string_member_of_a_union_is_checked(self):
        with pytest.raises(ValidationError, match=MESSAGE):
            Everything(union="a\nb")

    def test_a_value_on_one_line_is_untouched(self):
        value = "spaces, tabs\tand punctuation:;#\"'"
        assert Everything(plain=value).plain == value

    def test_a_relaxed_model_nested_in_a_checked_one_keeps_its_own_rule(self):
        assert Everything(relaxed={"anything": "a\nb"}).relaxed.anything == "a\nb"


class TestMultiline:
    @pytest.mark.parametrize(
        "field",
        [
            "marked",
            "non_empty",
            "long",
            "long_non_empty",
            "constrained",
            "optional",
            "not_required",
        ],
    )
    @pytest.mark.parametrize("break_", BREAKS)
    def test_a_marked_string_keeps_its_breaks(self, field, break_):
        value = f"first{break_}second"
        assert getattr(Marked(**{field: value}), field) == value

    @pytest.mark.parametrize("break_", BREAKS)
    def test_the_marker_applies_at_any_depth(self, break_):
        value = f"first{break_}second"
        model = Marked(in_list=[value], in_dict={"key": value}, secret=value)
        assert model.in_list == [value]
        assert model.in_dict == {"key": value}
        assert model.secret.get_secret_value() == value

    def test_the_marker_survives_a_for_update_model(self):
        """`ForUpdateMetaclass` folds field metadata into the annotation, which must not lose the marker."""
        assert MarkedForUpdate(marked="a\nb").marked == "a\nb"

    def test_a_marked_string_keeps_its_length_limit(self):
        with pytest.raises(ValidationError, match="at most 32 characters"):
            Marked(constrained="a\nb" * 20)

    def test_a_marked_non_empty_string_still_reports_a_string_error(self):
        """`MinLen` must constrain the string, or the message says "item" instead of "String"."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            Marked(non_empty="")

    def test_an_unmarked_string_of_the_same_model_is_still_checked(self):
        with pytest.raises(ValidationError, match=MESSAGE):
            Everything(plain="a\nb")


class TestTransform:
    @pytest.mark.parametrize(
        "name", ["cls", "choices", "config", "default", "fields", "metadata", "schema", "serialization", "type"]
    )
    def test_a_field_named_after_a_schema_key_is_still_checked(self, name):
        """A field name is a key of the `fields` map, so reading it as a key of a schema skips the field."""
        model = create_model(f"Named{name}", __base__=Checked, **{name: (str, Field(default=""))})
        with pytest.raises(ValidationError, match=MESSAGE):
            model(**{name: "a\nb"})

    def test_it_is_idempotent(self):
        once = add_line_break_validators(Everything.__pydantic_core_schema__)
        assert add_line_break_validators(once) == once

    def test_it_leaves_a_default_value_alone(self):
        """A default holds a caller's value, and a dict that looks like a schema must not be rewritten."""

        class WithDictDefault(Checked):
            looks_like_a_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "str"})

        assert WithDictDefault().looks_like_a_schema == {"type": "str"}

    def test_a_checked_model_still_publishes_a_json_schema(self):
        assert Everything.model_json_schema()["properties"]["plain"]["type"] == "string"


class TestUPS:
    """A UPS field that a NUT template interpolates bare is where the ban started, so it stays covered."""

    @pytest.mark.parametrize("field", UPS_SINGLE_LINE_FIELDS)
    def test_update_rejects_a_line_break(self, field):
        with pytest.raises(ValueError, match=MESSAGE):
            UPSUpdate(**{field: 'ups\nSHUTDOWNCMD "/bin/sh -c id"'})

    @pytest.mark.parametrize("field", UPS_SINGLE_LINE_FIELDS)
    def test_the_entry_rejects_a_stored_line_break(self, field):
        stored = {
            "id": 1,
            "complete_identifier": "ups",
            "description": "",
            "driver": "d",
            "port": "p",
            "monpwd": "pw",
            "monuser": "u",
            "identifier": "ups",
            "remotehost": "h",
            "mode": "MASTER",
            "shutdown": "BATT",
            "options": "",
            "optionsupsd": "",
            "extrausers": "",
            "shutdowncmd": None,
            "rmonitor": True,
            "nocommwarntime": None,
            "remoteport": 3493,
            "shutdowntimer": 30,
            "hostsync": 15,
            "powerdown": True,
        }

        with pytest.raises(ValueError, match=MESSAGE):
            UPSEntry.model_validate(stored | {field: "legacy\nvalue"})

    def test_a_clean_value_repairs_the_field(self):
        assert UPSUpdate(description="clean").description == "clean"


def test_the_marked_ups_fields_are_still_marked():
    """The ban complements the `FullAdmin` markers; it does not replace them."""
    assert {".".join(field.path) for field in full_admin_payload_fields(UPSUpdateArgs)[1]} == {
        "extrausers",
        "options",
        "optionsupsd",
        "shutdowncmd",
    }
