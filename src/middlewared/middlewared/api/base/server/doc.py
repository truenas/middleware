import inspect
import re
from typing import Any

from pydantic import BaseModel

from middlewared.role import RoleManager
from middlewared.utils.pydantic_ import model_json_schema

from ..jsonschema import replace_refs
from .api import API
from .event import Event
from .method import Method

_LIST_MARKER_RE = re.compile(r"([-*+]|[0-9]+\.|#\.) ")


def _is_unindented_prose(block: list[str]) -> bool:
    """Whether a blank-line-delimited block is a plain prose paragraph to unwrap."""
    # Any indentation means the block is a literal block, block quote, table, or a
    # list/definition item with continuation lines: its line structure matters.
    if any(line[:1].isspace() for line in block):
        return False
    # Directives and list items rely on their line structure too.
    first = block[0]
    if first.startswith(".. ") or _LIST_MARKER_RE.match(first):
        return False
    return True


def reflow_docstring(doc: str) -> str:
    """Unwrap hard-wrapped prose paragraphs while leaving RST structure intact.

    Method docstrings are hard-wrapped for readability in source. A
    blank-line-delimited block of entirely unindented prose is joined into a single
    line so it reflows when rendered as HTML. Any block that carries indentation (a
    literal block, block quote, table, or a list/definition item with continuation
    lines) or that opens with a directive or list marker is left exactly as written,
    so its structure is preserved rather than mangled.
    """
    out: list[str] = []
    block: list[str] = []

    def flush():
        if not block:
            return
        if _is_unindented_prose(block):
            out.append(" ".join(line.strip() for line in block))
        else:
            out.extend(block)
        block.clear()

    for line in doc.split("\n"):
        if line.strip():
            block.append(line)
        else:
            flush()
            out.append("")

    flush()

    return "\n".join(out).strip()


class APIDump(BaseModel):
    version: str
    version_title: str
    methods: list["APIDumpMethod"]
    events: list["APIDumpEvent"]


class APIDumpMethod(BaseModel):
    name: str
    roles: list[str]
    doc: str | None
    schemas: dict[str, Any]
    removed_in: str | None
    input_pipes: bool = False
    output_pipes: bool = False
    check_pipes: bool = True


class APIDumpEvent(BaseModel):
    name: str
    roles: list[str]
    doc: str | None
    schemas: dict[str, Any]
    removed_in: str | None


class APIDumper:
    def __init__(self, version: str, version_title: str, api: API, role_manager: RoleManager):
        self.version = version
        self.version_title = version_title
        self.api = api
        self.role_manager = role_manager

    async def dump(self) -> APIDump:
        return APIDump(
            version=self.version,
            version_title=self.version_title,
            methods=await self._dump_methods(),
            events=self._dump_events(),
        )

    async def _dump_methods(self) -> list[APIDumpMethod]:
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

    async def _dump_method(self, method: Method) -> "APIDumpMethod | None":
        schemas = await self._dump_method_schemas(method)
        if schemas is None:
            return None

        name = method.name
        plugin, method_name = name.rsplit(".", 1)
        if method_name in ("do_create", "do_update", "do_delete"):
            method_name = method_name[3:]
        name = f"{plugin}.{method_name}"

        methodobj_ = method.methodobj
        if doc := inspect.getdoc(methodobj_):
            doc = reflow_docstring(doc)

        input_pipes, output_pipes, check_pipes = False, False, True
        if job := getattr(methodobj_, "_job", None):
            pipes = job["pipes"]
            input_pipes = "input" in pipes
            output_pipes = "output" in pipes
            check_pipes = job["check_pipes"]

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
            input_pipes=input_pipes,
            output_pipes=output_pipes,
            check_pipes=check_pipes
        )

    async def _dump_method_schemas(self, method: Method) -> dict[str, Any] | None:
        accepts_model = await method.accepts_model()
        returns_model = await method.returns_model()
        if accepts_model is None or returns_model is None:
            return None

        accepts_json_schema = model_json_schema(accepts_model)
        accepts_json_schema = replace_refs(accepts_json_schema)

        returns_json_schema = model_json_schema(returns_model, mode="serialization")
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

    def _dump_events(self) -> list[APIDumpEvent]:
        result = []
        for event in self.api.events:
            if event.event["private"]:
                continue

            if not event.event["models"]:
                continue

            result.append(self._dump_event(event))

        return sorted(result, key=lambda event: event.name)

    def _dump_event(self, event: Event) -> APIDumpEvent:
        return APIDumpEvent(
            name=event.name,
            roles=sorted(self.role_manager.atomic_roles_for_event(event.name)),
            doc=event.event["description"],
            schemas=self._dump_event_schemas(event),
            removed_in=None,
        )

    def _dump_event_schemas(self, event: Event) -> dict[str, Any]:
        properties = {}
        for name, model in event.event["models"].items():
            schema = model_json_schema(model)
            schema = replace_refs(schema)
            properties[name] = schema

        return {
            "type": "object",
            "properties": properties,
        }
