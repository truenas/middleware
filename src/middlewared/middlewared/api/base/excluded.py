import typing
from typing import Any, NoReturn

from pydantic import Field, GetCoreSchemaHandler
from pydantic.json_schema import SkipJsonSchema
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

from middlewared.utils.lang import undefined

__all__ = ["Excluded", "excluded_field"]


class ExcludedField(Any):  # type: ignore[misc]
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        def validate(value: typing.Any, info: typing.Any) -> NoReturn:
            raise PydanticCustomError("", "Extra inputs are not permitted")

        return core_schema.with_info_after_validator_function(validate, handler(Any))


Excluded = SkipJsonSchema[ExcludedField]


def excluded_field() -> Excluded:
    return Field(default=undefined, exclude=True)  # type: ignore[return-value]
