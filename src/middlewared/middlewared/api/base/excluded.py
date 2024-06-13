from typing import Any

from pydantic_core import CoreSchema, core_schema, PydanticCustomError
from pydantic import Field, GetCoreSchemaHandler
from pydantic.json_schema import SkipJsonSchema

from middlewared.utils.lang import undefined

__all__ = ["excluded", "excluded_field"]


class ExcludedField(Any):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        def validate(value, info):
            raise PydanticCustomError("", "Extra inputs are not permitted")

        return core_schema.with_info_after_validator_function(validate, handler(Any))


def excluded():
    return SkipJsonSchema[ExcludedField]


def excluded_field():
    return Field(default=undefined, exclude=True)
