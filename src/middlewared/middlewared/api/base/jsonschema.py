from typing import TypeVar, TYPE_CHECKING

from middlewared.utils.pydantic_ import model_json_schema

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel


_PartialSchema = TypeVar("_PartialSchema")


def get_json_schema(model: type["BaseModel"]) -> list:
    schema = model_json_schema(model)
    schema = replace_refs(schema)
    schema = add_attrs(schema)

    return [schema["properties"][name] for name in model.schema_model_fields()]


def replace_refs(data: _PartialSchema, defs: dict | None = None) -> _PartialSchema:
    """Recursively replace all refs in the given schema with their respective definitions.

    :param data: JSON schema. Contents are not preserved.
    :return: The new JSON schema with refs replaced by their definitions.
    """
    if isinstance(data, dict):
        defs = data.pop("$defs", defs)
        if "$ref" in data:
            ref = data.pop("$ref")
            data = {**defs[ref.removeprefix("#/$defs/")], **data}

        return {k: replace_refs(v, defs) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_refs(v, defs) for v in data]
    else:
        return data


def add_attrs(schema: _PartialSchema) -> _PartialSchema:
    # FIXME: This is only here for backwards compatibility and should be removed eventually
    if isinstance(schema, dict):
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            schema = {
                **schema,
                "_attrs_order_": list(schema["properties"].keys()),
                "properties": {
                    k: {
                        **v,
                        "title": k,
                        "_name_": k,
                        "_required_": k in schema.get("required", [])
                    }
                    for k, v in schema["properties"].items()
                },
            }

        if schema.get("type") == "array" and "items" in schema and not isinstance(schema["items"], list):
            schema["items"] = [schema["items"]]  # FIXME: Non-standard compliant

        return {k: add_attrs(v) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [add_attrs(s) for s in schema]
    else:
        return schema
