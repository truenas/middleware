from __future__ import annotations

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
    "NetbiosName", "SnapshotNameSchema", "EmailString", "SmbShareName", "UUIDv4String",
]


def uuidv4_validator(value: str) -> str:
    try:
        uuid.UUID(value, version=4)
    except ValueError:
        raise ValueError('UUID is not valid version 4')

    return value


if TYPE_CHECKING:
    HttpUrl = str
else:
    HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]

# By default, our strings are no more than 1024 characters long. This string is 2**31-1 characters long (SQLite limit).
LongString = Annotated[str, MaxLen(2 ** 31 - 1)]
NonEmptyString = Annotated[str, MinLen(1)]
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
UUIDv4String = Annotated[str, AfterValidator(uuidv4_validator)]
