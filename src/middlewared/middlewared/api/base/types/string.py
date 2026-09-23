from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated
import uuid

from annotated_types import MaxLen, MinLen
from pydantic import (
    AfterValidator,
)
from pydantic import (
    HttpUrl as _HttpUrl,
)
from zettarepl.snapshot.name import validate_snapshot_naming_schema

from middlewared.api.base.types.json_schema import JsonSchemaExtra
from middlewared.api.base.validators import email_validator, time_validator
from middlewared.utils.netbios import validate_netbios_domain, validate_netbios_name
from middlewared.utils.smb import validate_smb_share_name

__all__ = [
    "HttpUrl", "LongString", "NonEmptyString", "LongNonEmptyString", "SECRET_VALUE", "TimeString", "NetbiosDomain",
    "NetbiosName", "SnapshotNameSchema", "EmailString", "SmbShareName", "SingleLineString", "SingleLineNonEmptyString",
    "LibvirtUUID",
]

_UUID_HEX = re.compile(r'[0-9a-fA-F]{32}')


def validate_single_line(value: str) -> str:
    """Reject a line break.

    For a field whose value is interpolated into a line-oriented configuration file. Such a field is not
    free-form -- a line break in it lets the caller append directives of their own to the generated file.
    """
    if "\n" in value or "\r" in value:
        raise ValueError("Line breaks are not allowed")

    return value


def normalize_libvirt_uuid(value: str) -> str:
    """Accept what libvirt accepts, and store it the way libvirt will report it.

    `virUUIDParse` takes 32 hexadecimal digits with hyphens ignored, so it rejects the braced and
    `urn:uuid:` forms that `uuid.UUID` strips -- a domain spelled either way can never be defined.
    Only a create model may use this: an entry model has to read back whatever is stored, and the
    stored string is the libvirt domain name, so normalizing on the way out would rewrite the name
    libvirt knows a defined domain by.
    """
    hexed = value.replace('-', '')
    if not _UUID_HEX.fullmatch(hexed):
        raise ValueError(
            'UUID must be 32 hexadecimal digits, optionally hyphenated '
            '(e.g. 550e8400-e29b-41d4-a716-446655440000)'
        )

    return str(uuid.UUID(hexed))


if TYPE_CHECKING:
    HttpUrl = str
else:
    HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]

SingleLineString = Annotated[str, AfterValidator(validate_single_line)]
# By default, our strings are no more than 1024 characters long. This string is 2**31-1 characters long (SQLite limit).
LongString = Annotated[str, MaxLen(2 ** 31 - 1)]
NonEmptyString = Annotated[str, MinLen(1)]
SingleLineNonEmptyString = Annotated[str, MinLen(1), AfterValidator(validate_single_line)]
LongNonEmptyString = Annotated[LongString, MinLen(1)]
TimeString = Annotated[
    str, AfterValidator(time_validator), JsonSchemaExtra(examples=["00:00", "06:30", "18:00", "23:00"])
]
EmailString = Annotated[str, AfterValidator(email_validator)]
NetbiosDomain = Annotated[str, AfterValidator(validate_netbios_domain)]
NetbiosName = Annotated[str, AfterValidator(validate_netbios_name)]
SmbShareName = Annotated[str, AfterValidator(validate_smb_share_name)]
SnapshotNameSchema = Annotated[str, AfterValidator(lambda val: validate_snapshot_naming_schema(val) or val)]
SECRET_VALUE = "********"
LibvirtUUID = Annotated[str, AfterValidator(normalize_libvirt_uuid)]
