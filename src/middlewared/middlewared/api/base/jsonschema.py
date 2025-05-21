__all__ = ["get_json_schema"]


def get_json_schema(model):
    schema = model.model_json_schema()
    schema = clean_schema(schema, schema.get("$defs", {}))
    schema = add_attrs(schema)

    return [schema["properties"][name] for name in model.schema_model_fields()]


def clean_schema(schema: dict, defs: dict | None = None) -> dict:
    return _clean_field_descriptions(_replace_refs(schema, defs))


def _replace_refs(data, defs: dict | None = None):
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


def _clean_field_descriptions(schema: dict) -> dict:
    """Remove single newlines from field descriptions and replace double newlines with single newlines.

    Solves the issue of docstring field descriptions that wrap to the next line having an unwanted newline
    character when rendered in the docs.

    :param field_schema: `model.model_json_schema()`
    """
    for field_schema in schema["properties"].values():
        if descr := field_schema.get("description"):
            NEWLINE = "$placeholder$"
            field_schema["description"] = descr.replace("\n\n", NEWLINE).replace("\n", " ").replace(NEWLINE, "\n")

    return schema


def add_attrs(schema):
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
                    for k, v in schema["properties"].items()},
            }

        if schema.get("type") == "array" and "items" in schema and not isinstance(schema["items"], list):
            schema["items"] = [schema["items"]]  # FIXME: Non-standard compliant

        return {k: add_attrs(v) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [add_attrs(s) for s in schema]
    else:
        return schema
