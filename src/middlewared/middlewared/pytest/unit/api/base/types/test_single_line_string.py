from pydantic import Field
import pytest

from middlewared.api.base import BaseModel, SingleLineNonEmptyString, SingleLineString
from middlewared.api.base.handler.full_admin import full_admin_payload_fields
from middlewared.api.v27_0_0.ups import UPSEntry, UPSUpdate, UPSUpdateArgs

# Every UPS field that a template interpolates bare into `ups.conf`, `upsd.users` or `upsmon.conf`. A line
# break in one lets the caller append directives of their own -- including the `SHUTDOWNCMD` that
# `UPSEntry.shutdowncmd` is marked `FullAdmin` to protect.
UPS_SINGLE_LINE_FIELDS = ("description", "driver", "identifier", "monpwd", "monuser", "port", "remotehost")

BREAKS = ("\n", "\r", "\r\n")


class Model(BaseModel):
    one_line: SingleLineString = Field(default="")
    required: SingleLineNonEmptyString = Field(default="x")


class TestSingleLineString:
    @pytest.mark.parametrize("value", ["", "plain", "with spaces", "tab\tseparated", "punctuation:;#\"'"])
    def test_accepts_anything_on_one_line(self, value):
        assert Model(one_line=value).one_line == value

    @pytest.mark.parametrize("break_", BREAKS)
    @pytest.mark.parametrize("shape", ["lead{b}ing", "{b}leading", "trailing{b}"])
    def test_rejects_a_line_break_anywhere(self, break_, shape):
        with pytest.raises(ValueError, match="Line breaks are not allowed"):
            Model(one_line=shape.format(b=break_))

    def test_the_non_empty_variant_still_reports_a_string_error(self):
        """`MinLen` must constrain the string, not the validator's output, or the message says "item"."""
        with pytest.raises(ValueError, match="String should have at least 1 character"):
            Model(required="")


class TestUPSFields:
    """The constraint is on the write model only, so a value stored before it existed stays reachable."""

    @pytest.mark.parametrize("field", UPS_SINGLE_LINE_FIELDS)
    def test_update_rejects_a_line_break(self, field):
        with pytest.raises(ValueError, match="Line breaks are not allowed"):
            UPSUpdate(**{field: 'ups\nSHUTDOWNCMD "/bin/sh -c id"'})

    @pytest.mark.parametrize("field", UPS_SINGLE_LINE_FIELDS)
    def test_the_entry_still_reads_a_stored_line_break(self, field):
        """`ups.config` and `ups.update` both start by reading the entry; constraining it would brick both."""
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

        assert UPSEntry.model_validate(stored | {field: "legacy\nvalue"})

    def test_a_clean_value_repairs_the_field(self):
        assert UPSUpdate(description="clean").description == "clean"


def test_the_marked_ups_fields_are_still_marked():
    """The single-line sweep complements the `FullAdmin` markers; it does not replace them."""
    assert {".".join(field.path) for field in full_admin_payload_fields(UPSUpdateArgs)[1]} == {
        "extrausers",
        "options",
        "optionsupsd",
        "shutdowncmd",
    }
