from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    GetCoreSchemaHandler,
    HttpUrl as _HttpUrl,
    PlainSerializer,
)
from pydantic_core import CoreSchema, core_schema, PydanticKnownError

from middlewared.api.base.validators import time_validator, email_validator
from middlewared.utils.netbios import validate_netbios_name, validate_netbios_domain
from middlewared.utils.smb import validate_smb_share_name
from zettarepl.snapshot.name import validate_snapshot_naming_schema


__all__ = [
    "HttpUrl", "LongString", "NonEmptyString", "LongNonEmptyString", "SECRET_VALUE", "TimeString", "NetbiosDomain",
    "NetbiosName", "SnapshotNameSchema", "EmailString", "SmbShareName",
]


class LongStringWrapper:
    """
    We have to box our long strings in this class to bypass the global limit for string length.
    """

    max_length = 2048000  # historic maximum length of string in filesystem.file_receive

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


HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]
# By default, our strings are no more than 1024 characters long. This string is 2**31-1 characters long (SQLite limit).
LongString = Annotated[
    LongStringWrapper,
    BeforeValidator(LongStringWrapper),
    PlainSerializer(lambda x: x.value if isinstance(x, LongStringWrapper) else x),
]
NonEmptyString = Annotated[str, Field(min_length=1)]
LongNonEmptyString = Annotated[LongString, Field(min_length=1)]
TimeString = Annotated[str, AfterValidator(time_validator), Field(examples=["00:00", "06:30", "18:00", "23:00"])]
EmailString = Annotated[str, AfterValidator(email_validator)]
NetbiosDomain = Annotated[str, AfterValidator(validate_netbios_domain)]
NetbiosName = Annotated[str, AfterValidator(validate_netbios_name)]
SmbShareName = Annotated[str, AfterValidator(validate_smb_share_name)]
SnapshotNameSchema = Annotated[str, AfterValidator(lambda val: validate_snapshot_naming_schema(val) or val)]
SECRET_VALUE = "********"
