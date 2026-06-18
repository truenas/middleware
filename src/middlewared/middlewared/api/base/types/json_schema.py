from typing import Any

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

__all__ = ["JsonSchemaExtra"]


class JsonSchemaExtra:
    """Annotated metadata that merges extra keys into a field's generated JSON schema.

    Use this instead of ``Field(examples=..., json_schema_extra=...)`` inside a *shared*
    ``Annotated`` type alias. ``Field(...)`` produces a single ``FieldInfo`` instance that
    is reused by every model field referencing the alias. Pydantic's field-merge machinery
    shallow-copies that ``FieldInfo`` and shares its ``_attributes_set`` dict, so a stray
    ``default`` recorded for one consumer leaks into all the others (silently turning
    required fields optional). ``JsonSchemaExtra`` is a plain immutable metadata object with
    no such mutable state, so it is safe to embed in a shared alias.
    """

    __slots__ = ("extra",)

    def __init__(self, **extra: Any) -> None:
        self.extra = extra

    def __get_pydantic_json_schema__(self, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema.update(self.extra)
        return json_schema
