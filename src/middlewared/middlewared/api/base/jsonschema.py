__all__ = ["get_json_schema"]


def get_json_schema(model):
    schema = model.model_json_schema()
    schema = replace_refs(schema, schema.get("$defs", {}))
    schema = add_attrs(schema)

    return [schema["properties"][field] for field in model.model_fields]


def replace_refs(data, defs=None):
    if isinstance(data, dict):
        if "$ref" in data:
            ref = data.pop("$ref")
            data = {**defs[ref.removeprefix("#/$defs/")], **data}

        return {k: replace_refs(v, defs) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_refs(v, defs) for v in data]
    else:
        return data


def add_attrs(schema):
    # FIXME: This is only here for backwards compatibility and should be removed eventually
    if isinstance(schema, dict):
        if isinstance(schema.get("properties"), dict):
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
