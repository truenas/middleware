import inspect
import re

from pydantic import BaseModel

from middlewared.role import RoleManager
from ..jsonschema import replace_refs
from .api import API
from .event import Event
from .method import Method


class APIDump(BaseModel):
    version: str
    version_title: str
    methods: list["APIDumpMethod"]
    events: list["APIDumpEvent"]


class APIDumpMethod(BaseModel):
    name: str
    roles: list[str]
    doc: str | None
    schemas: dict
    removed_in: str | None


class APIDumpEvent(BaseModel):
    name: str
    roles: list[str]
    doc: str | None
    schemas: dict
    removed_in: str | None


class APIDumper:
    def __init__(self, version: str, version_title: str, api: API, role_manager: RoleManager):
        self.version = version
        self.version_title = version_title
        self.api = api
        self.role_manager = role_manager

    async def dump(self):
        return APIDump(
            version=self.version,
            version_title=self.version_title,
            methods=await self._dump_methods(),
            events=self._dump_events(),
        )

    async def _dump_methods(self):
        result = []
        for method in self.api.methods:
            if method.serviceobj._config.private:
                continue

            if getattr(method.methodobj, "_private", False):
                continue

            if not hasattr(method.methodobj, "new_style_accepts"):
                continue

            method_dump = await self._dump_method(method)
            if method_dump is None:
                continue

            result.append(method_dump)

        return sorted(result, key=lambda method: method.name)

    async def _dump_method(self, method: Method):
        schemas = await self._dump_method_schemas(method)
        if schemas is None:
            return None

        name = method.name
        plugin, method_name = name.rsplit(".", 1)
        if method_name in ("do_create", "do_update", "do_delete"):
            method_name = method_name[3:]
        name = f"{plugin}.{method_name}"

        if doc := inspect.getdoc(method.methodobj):
            doc = re.sub(r"(\S)\n[ ]*(\S)", "\\1 \\2", doc).strip()

        if hasattr(method, "_job"):
            # FIXME: If we decide to keep the jobs, make this nicer (a badge?)
            if doc:
                doc = doc + "\r\n\r\n"
            else:
                doc = ""

            doc += "This method is a job."

        return APIDumpMethod(
            name=name,
            roles=sorted(self.role_manager.atomic_roles_for_method(name)),
            doc=doc,
            schemas=schemas,
            removed_in=getattr(method.methodobj, "_removed_in", None),
        )

    async def _dump_method_schemas(self, method: Method):
        accepts_model = await method.accepts_model()
        returns_model = await method.returns_model()
        if accepts_model is None or returns_model is None:
            return None

        accepts_json_schema = accepts_model.model_json_schema()
        accepts_json_schema = replace_refs(accepts_json_schema)

        returns_json_schema = returns_model.model_json_schema(mode="serialization")
        returns_json_schema = replace_refs(returns_json_schema)

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
                        for field in accepts_model.schema_model_fields()
                    ],
                    "items": False,
                },
                "Return value": {
                    **returns_json_schema["properties"]["result"],
                },
            },
        }

    def _dump_events(self):
        result = []
        for event in self.api.events:
            if event.event["private"]:
                continue

            if not event.event["models"]:
                continue

            result.append(self._dump_event(event))

        return sorted(result, key=lambda event: event.name)

    def _dump_event(self, event: Event):
        return APIDumpEvent(
            name=event.name,
            roles=sorted(self.role_manager.atomic_roles_for_event(event.name)),
            doc=event.event["description"],
            schemas=self._dump_event_schemas(event),
            removed_in=None,
        )

    def _dump_event_schemas(self, event: Event):
        properties = {}
        for name, model in event.event["models"].items():
            schema = model.model_json_schema()
            schema = replace_refs(schema)
            properties[name] = schema

        return {
            "type": "object",
            "properties": properties,
        }
