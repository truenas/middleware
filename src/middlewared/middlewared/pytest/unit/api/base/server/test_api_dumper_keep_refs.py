import typing

from pydantic import Field
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.server.doc import APIDumper


class KeepRefsSharedOptions(BaseModel):
    verbose: bool = False


class KeepRefsPasswordLogin(BaseModel):
    mechanism: typing.Literal["PASSWORD_PLAIN"]
    username: str
    options: KeepRefsSharedOptions = Field(default_factory=KeepRefsSharedOptions)


class KeepRefsTokenLogin(BaseModel):
    mechanism: typing.Literal["TOKEN_PLAIN"]
    token: str


class KeepRefsTestArgs(BaseModel):
    login_data: typing.Annotated[KeepRefsPasswordLogin | KeepRefsTokenLogin, Field(discriminator="mechanism")]
    options: KeepRefsSharedOptions = Field(default_factory=KeepRefsSharedOptions)


class KeepRefsTestResult(BaseModel):
    result: KeepRefsSharedOptions


class FakeMethod:
    def __init__(self, accepts, returns):
        self._accepts = accepts
        self._returns = returns

    async def accepts_model(self):
        return self._accepts

    async def returns_model(self):
        return self._returns


class FakeEvent:
    def __init__(self, models):
        self.name = "test.event"
        self.event = {"models": models, "description": "Test event", "private": False}


def make_dumper(keep_refs):
    return APIDumper("v1.0", "v1.0 (current)", api=None, role_manager=None, keep_refs=keep_refs)


def collect_refs(schema, refs=None):
    """Collect every `$ref` target and `discriminator.mapping` target in the document."""
    if refs is None:
        refs = []
    if isinstance(schema, dict):
        for k, v in schema.items():
            if k == "$ref":
                refs.append(v)
            elif k == "discriminator" and isinstance(v, dict):
                refs.extend(v.get("mapping", {}).values())
            collect_refs(v, refs)
    elif isinstance(schema, list):
        for v in schema:
            collect_refs(v, refs)
    return refs


def assert_refs_resolve(document):
    defs = document.get("$defs", {})
    refs = collect_refs(document)
    assert refs, "expected the document to contain references"
    for ref in refs:
        assert ref.startswith("#/$defs/"), ref
        assert ref.removeprefix("#/$defs/") in defs, f"{ref} does not resolve"


@pytest.mark.asyncio
async def test_keep_refs_method_schemas():
    schemas = await make_dumper(keep_refs=True)._dump_method_schemas(FakeMethod(KeepRefsTestArgs, KeepRefsTestResult))

    assert set(schemas) == {"accepts", "returns"}

    accepts = schemas["accepts"]
    # Model identities are preserved: the document is titled after the model and named
    # definitions are kept in the `$defs` table instead of being inlined anonymously.
    assert accepts["title"] == "KeepRefsTestArgs"
    for name in ("KeepRefsSharedOptions", "KeepRefsPasswordLogin", "KeepRefsTokenLogin"):
        assert name in accepts["$defs"]

    # Every `$ref` and every `discriminator.mapping` target resolves within the document.
    assert_refs_resolve(accepts)
    mapping = accepts["properties"]["login_data"]["discriminator"]["mapping"]
    assert mapping == {
        "PASSWORD_PLAIN": "#/$defs/KeepRefsPasswordLogin",
        "TOKEN_PLAIN": "#/$defs/KeepRefsTokenLogin",
    }

    # Positional call parameters are derivable from the properties order.
    assert list(accepts["properties"]) == list(KeepRefsTestArgs.schema_model_fields())

    assert_refs_resolve(schemas["returns"])


@pytest.mark.asyncio
async def test_default_method_schemas_are_inlined():
    schemas = await make_dumper(keep_refs=False)._dump_method_schemas(FakeMethod(KeepRefsTestArgs, KeepRefsTestResult))

    assert set(schemas["properties"]) == {"Call parameters", "Return value"}
    assert "$defs" not in schemas

    def assert_no_refs(schema):
        if isinstance(schema, dict):
            assert "$ref" not in schema
            for v in schema.values():
                assert_no_refs(v)
        elif isinstance(schema, list):
            for v in schema:
                assert_no_refs(v)

    assert_no_refs(schemas["properties"]["Call parameters"]["prefixItems"])
    assert_no_refs(schemas["properties"]["Return value"].get("properties"))


def test_keep_refs_event_schemas():
    schemas = make_dumper(keep_refs=True)._dump_event_schemas(FakeEvent({"ADDED": KeepRefsPasswordLogin}))

    assert set(schemas) == {"ADDED"}
    assert schemas["ADDED"]["title"] == "KeepRefsPasswordLogin"
    assert "KeepRefsSharedOptions" in schemas["ADDED"]["$defs"]
    assert_refs_resolve(schemas["ADDED"])


def test_default_event_schemas_are_inlined():
    schemas = make_dumper(keep_refs=False)._dump_event_schemas(FakeEvent({"ADDED": KeepRefsPasswordLogin}))

    assert set(schemas["properties"]) == {"ADDED"}
    assert "$defs" not in schemas["properties"]["ADDED"]
    assert "$ref" not in str(schemas["properties"]["ADDED"].get("properties", {}))
