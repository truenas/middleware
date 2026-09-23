import re
from typing import Annotated, Any
import uuid

from annotated_types import MinLen
from pydantic import (
    AfterValidator,
    BeforeValidator,
    GetCoreSchemaHandler,
    HttpUrl as _HttpUrl,
    PlainSerializer,
)
from pydantic_core import CoreSchema, core_schema, PydanticKnownError

from middlewared.api.base.types.json_schema import JsonSchemaExtra
from middlewared.api.base.validators import time_validator, email_validator
from middlewared.utils.netbios import validate_netbios_name, validate_netbios_domain
from middlewared.utils.smb import validate_smb_share_name
from zettarepl.snapshot.name import validate_snapshot_naming_schema


__all__ = [
    "HttpUrl", "LongString", "NonEmptyString", "LongNonEmptyString", "SECRET_VALUE", "TimeString", "NetbiosDomain",
    "NetbiosName", "SnapshotNameSchema", "EmailString", "SmbShareName", "LibvirtUUID",
]

_UUID_HEX = re.compile(r'[0-9a-fA-F]{32}')


class LongStringWrapper:
    """
    We have to box our long strings in this class to bypass the global limit for string length.
    """

    max_length = 2048000  # historic maximum length of string in filesystem.file_receive
    __normalize_as__ = str

    def __init__(self, value):
        if isinstance(value, LongStringWrapper):
            value = value.value

        if not isinstance(value, str):
            raise PydanticKnownError("string_type")

        if len(value) > self.max_length:
            raise PydanticKnownError("string_too_long", {"max_length": self.max_length})

        self.value = value

    def __len__(self):
        return len(self.value)

    def __eq__(self, other):
        return isinstance(other, LongStringWrapper) and self.value == other.value

    def __repr__(self):
        return f"LongStringWrapper({self.value})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.no_info_after_validator_function(
                cls,
                core_schema.is_instance_schema(LongStringWrapper),
            ),
        )


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


HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]
# By default, our strings are no more than 1024 characters long. This string is 2**31-1 characters long (SQLite limit).
LongString = Annotated[
    LongStringWrapper,
    BeforeValidator(LongStringWrapper),
    PlainSerializer(lambda x: x.value if isinstance(x, LongStringWrapper) else x),
]
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
LibvirtUUID = Annotated[str, AfterValidator(normalize_libvirt_uuid)]
