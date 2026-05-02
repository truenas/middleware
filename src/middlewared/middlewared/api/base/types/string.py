from typing import Annotated
import uuid

from pydantic import (
    AfterValidator,
    Field,
)
from pydantic import (
    HttpUrl as _HttpUrl,
)
from zettarepl.snapshot.name import validate_snapshot_naming_schema

from middlewared.api.base.validators import email_validator, time_validator
from middlewared.utils.netbios import validate_netbios_domain, validate_netbios_name
from middlewared.utils.smb import validate_smb_share_name

__all__ = [
    "HttpUrl", "LongString", "NonEmptyString", "LongNonEmptyString", "SECRET_VALUE", "TimeString", "NetbiosDomain",
    "NetbiosName", "SnapshotNameSchema", "EmailString", "SmbShareName", "UUIDv4String",
]


def uuidv4_validator(value):
    try:
        uuid.UUID(value, version=4)
    except ValueError:
        raise ValueError('UUID is not valid version 4')

    return value


HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]
# By default, our strings are no more than 1024 characters long. This string is 2**31-1 characters long (SQLite limit).
LongString = Annotated[str, Field(max_length=2 ** 31 - 1)]
NonEmptyString = Annotated[str, Field(min_length=1)]
LongNonEmptyString = Annotated[LongString, Field(min_length=1)]
TimeString = Annotated[str, AfterValidator(time_validator), Field(examples=["00:00", "06:30", "18:00", "23:00"])]
EmailString = Annotated[str, AfterValidator(email_validator)]
NetbiosDomain = Annotated[str, AfterValidator(validate_netbios_domain)]
NetbiosName = Annotated[str, AfterValidator(validate_netbios_name)]
SmbShareName = Annotated[str, AfterValidator(validate_smb_share_name)]
SnapshotNameSchema = Annotated[str, AfterValidator(lambda val: validate_snapshot_naming_schema(val) or val)]
SECRET_VALUE = "********"
UUIDv4String = Annotated[str, AfterValidator(uuidv4_validator)]
