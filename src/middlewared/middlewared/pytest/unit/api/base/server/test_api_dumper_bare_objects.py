import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NotRequired, query_result_item

from .test_api_dumper_keep_refs import FakeMethod, make_dumper


class BareOptions(BaseModel):
    verbose: bool = False


class BareEntry(BaseModel):
    id: int
    name: str = NotRequired
    options: BareOptions = NotRequired


class BareUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    name: str
    options: BareOptions


class BareResultData(BaseModel):
    entry: BareEntry
    updated: BareUpdate
    queried: list[query_result_item(BareEntry)]


class BareTestArgs(BaseModel):
    data: BareUpdate


class BareTestResult(BaseModel):
    result: BareResultData


def find_bare_objects(schema, path="$"):
    """Paths of every node that declares `type: object` but describes no members.

    A model that declares fields must never dump this way. It means the schema was derived
    from something other than the fields, and a client generated from the dump sees an
    opaque object where the model has a known shape.
    """
    bare = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and not any(
            k in schema for k in ("properties", "additionalProperties", "patternProperties")
        ):
            return [path]
        for k, v in schema.items():
            bare += find_bare_objects(v, f"{path}.{k}")
    elif isinstance(schema, list):
        for i, v in enumerate(schema):
            bare += find_bare_objects(v, f"{path}[{i}]")
    return bare


@pytest.mark.asyncio
async def test_dumped_schemas_have_no_bare_objects():
    schemas = await make_dumper(keep_refs=False)._dump_method_schemas(FakeMethod(BareTestArgs, BareTestResult))

    # None of these models has a `dict`-typed field, so every object node has fields to describe.
    assert find_bare_objects(schemas) == []
