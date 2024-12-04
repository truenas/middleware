from typing import Any

from pydantic import AfterValidator, BeforeValidator, Field, GetCoreSchemaHandler, HttpUrl as _HttpUrl, PlainSerializer
from pydantic_core import CoreSchema, core_schema, PydanticKnownError
from typing_extensions import Annotated

from middlewared.utils.netbios import validate_netbios_name, validate_netbios_domain
from middlewared.validators import Time

__all__ = ["HttpUrl", "LongString", "NonEmptyString", "LongNonEmptyString", "SECRET_VALUE", "TimeString", "NetbiosDomain", "NetbiosName"]

HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]


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


# By default, our strings are no more than 1024 characters long. This string is 2**31-1 characters long (SQLite limit).
LongString = Annotated[
    LongStringWrapper,
    BeforeValidator(LongStringWrapper),
    PlainSerializer(lambda x: x.value if isinstance(x, LongStringWrapper) else x),
]

NonEmptyString = Annotated[str, Field(min_length=1)]
LongNonEmptyString = Annotated[LongString, Field(min_length=1)]
TimeString = Annotated[str, AfterValidator(Time())]
NetbiosDomain = Annotated[str, AfterValidator(validate_netbios_domain)]
NetbiosName = Annotated[str, AfterValidator(validate_netbios_name)]

SECRET_VALUE = "********"
