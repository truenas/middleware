from typing import TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel


_PartialSchema = TypeVar("_PartialSchema")


def get_json_schema(model: type["BaseModel"]) -> list:
    schema = model.model_json_schema()
    schema = clean_schema(schema)
    schema = _add_attrs(schema)

    return [schema["properties"][name] for name in model.schema_model_fields()]


def clean_schema(schema: dict) -> dict:
    """Prepare JSON schema for parsing.

    Replace references with their definitions, remove single newlines from field descriptions, and replace double
    newlines with single newlines.

    :param field_schema: A JSON schema like the return of `model.model_json_schema()`.
    :return: The cleaned JSON schema.
    """
    schema = _replace_refs(schema)
    _clean_descriptions(schema)
    return schema


def _replace_refs(data: _PartialSchema, defs: dict | None = None) -> _PartialSchema:
    """Recursively replace all refs in the given schema with their respective definitions.

    :param data: JSON schema. Contents are not preserved.
    :return: The new JSON schema with refs replaced by their definitions.
    """
    if isinstance(data, dict):
        defs = data.pop("$defs", defs)
        if "$ref" in data:
            ref = data.pop("$ref")
            data = {**defs[ref.removeprefix("#/$defs/")], **data}

        return {k: _replace_refs(v, defs) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_refs(v, defs) for v in data]
    else:
        return data


def _clean_descriptions(schema: dict) -> None:
    """Recursively remove single newlines and replace double newlines with single newlines.

    Solves the issue of docstring field descriptions that wrap to the next line having an unwanted newline
    character when rendered in the docs.

    :param schema: JSON schema with all references replaced by their definitions.
    """
    for field_schema in schema["properties"].values():
        if description := field_schema.get("description"):
            NEWLINE = "$placeholder$"
            field_schema["description"] = (
                description.replace("\n\n", NEWLINE).replace("\n", " ").replace(NEWLINE, "\n").strip()
            )
        if "properties" in field_schema:
            _clean_descriptions(field_schema)
        elif (field_items := field_schema.get("items")) and "properties" in field_items:
            _clean_descriptions(field_items)


def _add_attrs(schema: _PartialSchema) -> _PartialSchema:
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

        return {k: _add_attrs(v) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [_add_attrs(s) for s in schema]
    else:
        return schema
