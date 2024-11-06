import pytest

from middlewared.api.base import BaseModel, query_result
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter


class EntryV1(BaseModel):
    name: str


class EntryV2(BaseModel):
    first_name: str
    last_name: str

    @classmethod
    def to_previous(cls, value):
        return {"name": f"{value['first_name']} {value['last_name']}"}


QueryResultV1 = query_result(EntryV1)
QueryResultV2 = query_result(EntryV2)


@pytest.mark.parametrize("version1,value,version2,result", [
    ("v2", [{"first_name": "Ivan", "last_name": "Ivanov"}], "v1", [{"name": "Ivan Ivanov"}]),
    ("v2", {"first_name": "Ivan", "last_name": "Ivanov"}, "v1", {"name": "Ivan Ivanov"}),
    ("v2", 1, "v1", 1),
])
def test_adapt(version1, value, version2, result):
    adapter = APIVersionsAdapter([
        APIVersion("v1", {"Entry": EntryV1, "QueryResult": QueryResultV1,
                          "QueryResultItem": QueryResultV1.__annotations__["result"].__args__[1]}),
        APIVersion("v2", {"Entry": EntryV2, "QueryResult": QueryResultV2,
                          "QueryResultItem": QueryResultV1.__annotations__["result"].__args__[1]}),
    ])
    assert adapter.adapt({"result": value}, "QueryResult", version1, version2) == {"result": result}
