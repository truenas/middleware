import inspect
import re

from pydantic import BaseModel

from ..jsonschema import replace_refs
from .api import API
from .method import Method


class APIDump(BaseModel):
    version: str
    methods: list["APIDumpMethod"]


class APIDumpMethod(BaseModel):
    name: str
    doc: str | None
    schemas: dict


class APIDumper:
    def __init__(self, version: str, api: API):
        self.version = version
        self.api = api

    def dump(self):
        return APIDump(version=self.version, methods=self._dump_methods())

    def _dump_methods(self):
        result = []
        for method in self.api.methods:
            if not hasattr(method.methodobj, "new_style_accepts"):
                continue

            result.append(self._dump_method(method))

        return sorted(result, key=lambda method: method.name)

    def _dump_method(self, method: Method):
        name = method.name
        plugin, method_name = name.rsplit(".", 1)
        if method_name in ("do_create", "do_update", "do_delete"):
            method_name = method_name[3:]
        name = f"{plugin}.{method_name}"

        if doc := inspect.getdoc(method.methodobj):
            doc = re.sub(r"(\S)\n[ ]*(\S)", "\\1 \\2", doc)

        return APIDumpMethod(
            name=name,
            doc=doc,
            schemas=self._dump_method_schemas(method),
        )

    def _dump_method_schemas(self, method: Method):
        accepts_json_schema = method.methodobj.new_style_accepts.model_json_schema()
        accepts_json_schema = replace_refs(accepts_json_schema, accepts_json_schema.get("$defs", {}))

        returns_json_schema = method.methodobj.new_style_returns.model_json_schema(mode="serialization")
        returns_json_schema = replace_refs(returns_json_schema, returns_json_schema.get("$defs", {}))

        return {
            "type": "object",
            "properties": {
                "Call parameters": {
                    "type": "array",
                    "prefixItems": [
                        {
                            **accepts_json_schema["properties"][field],
                            "title": field,
                        }
                        for field in method.methodobj.new_style_accepts.model_fields
                    ],
                    "items": False,
                },
                "Return value": {
                    **returns_json_schema["properties"]["result"],
                },
            },
        }
