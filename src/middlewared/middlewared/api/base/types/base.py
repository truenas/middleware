from typing import Any, Generic, get_args, get_origin, TypeVar

from pydantic import AfterValidator, BeforeValidator, Field, GetCoreSchemaHandler, HttpUrl as _HttpUrl, PlainSerializer
from pydantic_core import CoreSchema, core_schema, PydanticKnownError
from typing_extensions import Annotated

from middlewared.utils.lang import undefined

__all__ = ["HttpUrl", "LongString", "NonEmptyString", "Private", "PRIVATE_VALUE"]

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

PrivateType = TypeVar("PrivateType")
PRIVATE_VALUE = "********"


class Private(Generic[PrivateType]):
    """
    Use this generic to declare model fields that should not be visible in debug logs and to non-admin users (e.g.
    passwords and other secrets).

    Under the hood it works the following way: when a pydantic model is serialized to JSON, the field is serialized
    as `********`; when a pydantic model is serialized in `python` mode, the field is returned as-is. Serialization
    mode is the only context pydantic provides when serializing a model.

    The code is a copypaste from `pydantic`'s `Secret` with `serialize` implementation modified.
    """

    def __init__(self, value: PrivateType) -> None:
        self.value: PrivateType = value

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type[Any], handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        inner_type = None
        # if origin_type is Private, then cls is a GenericAlias, and we can extract the inner type directly
        origin_type = get_origin(source)
        if origin_type is not None:
            inner_type = get_args(source)[0]
        # otherwise, we need to get the inner type from the base class
        else:
            bases = getattr(cls, "__orig_bases__", getattr(cls, "__bases__", []))
            for base in bases:
                if get_origin(base) is Private:
                    inner_type = get_args(base)[0]
            if bases == [] or inner_type is None:
                raise TypeError(
                    f"Can't get private type from {cls.__name__}. "
                    'Please use Private[<type>], or subclass from Private[<type>] instead.'
                )

        inner_schema = handler.generate_schema(inner_type)  # type: ignore

        def validate_secret_value(value, handler) -> Private[PrivateType]:
            if isinstance(value, Private):
                value = value.value
            validated_inner = handler(value)
            return cls(validated_inner)

        def serialize(value: Private[PrivateType], info: core_schema.SerializationInfo) -> str | None:
            if value == undefined:
                return undefined
            elif info.mode == "json":
                return PRIVATE_VALUE
            elif value is None:
                return None
            else:
                return value.value

        return core_schema.json_or_python_schema(
            python_schema=core_schema.no_info_wrap_validator_function(
                validate_secret_value,
                inner_schema,
            ),
            json_schema=core_schema.no_info_after_validator_function(lambda x: cls(x), inner_schema),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize,
                info_arg=True,
                when_used="always",
            ),
        )
