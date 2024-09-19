from typing import Any

from pydantic import AfterValidator, BeforeValidator, Field, GetCoreSchemaHandler, HttpUrl as _HttpUrl, PlainSerializer
from pydantic_core import CoreSchema, core_schema, PydanticKnownError
from typing_extensions import Annotated

from middlewared.utils.lang import undefined

__all__ = ["HttpUrl", "LongString", "NonEmptyString", "SECRET_VALUE"]

HttpUrl = Annotated[_HttpUrl, AfterValidator(str)]


class LongStringWrapper:
    """
    We have to box our long strings in this class to bypass the global limit for string length.
    """

    max_length = 2 ** 31 - 1

    def __init__(self, value):
        if isinstance(value, LongStringWrapper):
            value = value.value

        if not isinstance(value, str):
            raise PydanticKnownError("string_type")

        if len(value) > self.max_length:
            raise PydanticKnownError("string_too_long", {"max_length": self.max_length})

        self.value = value

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
    PlainSerializer(lambda x: undefined if x == undefined else x.value),
]

NonEmptyString = Annotated[str, Field(min_length=1)]

SECRET_VALUE = "********"
