import pytest

from middlewared.api.base import BaseModel, query_result
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.pytest.unit.helpers import TestModelProvider


class Entry(BaseModel):
    name: str


EntryV1 = Entry


class Entry(BaseModel):
    first_name: str
    last_name: str

    @classmethod
    def to_previous(cls, value):
        return {"name": f"{value['first_name']} {value['last_name']}"}


EntryV2 = Entry


QueryResultV1 = query_result(EntryV1)
QueryResultV2 = query_result(EntryV2)


@pytest.mark.asyncio
@pytest.mark.parametrize("version1,value,version2,result", [
    ("v2", [{"first_name": "Ivan", "last_name": "Ivanov"}], "v1", [{"name": "Ivan Ivanov"}]),
    ("v2", {"first_name": "Ivan", "last_name": "Ivanov"}, "v1", {"name": "Ivan Ivanov"}),
    ("v2", 1, "v1", 1),
])
async def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", TestModelProvider({
            "Entry": EntryV1,
            "QueryResult": QueryResultV1,
            "QueryResultItem": QueryResultV1.__annotations__["result"].__args__[1],
        })),
        APIVersion("v2", TestModelProvider({
            "Entry": EntryV2,
            "QueryResult": QueryResultV2,
            "QueryResultItem": QueryResultV1.__annotations__["result"].__args__[1]}
        )),
    ])
    assert await adapter.adapt({"result": value}, "QueryResult", version1, version2) == {"result": result}
