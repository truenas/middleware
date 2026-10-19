from contextlib import asynccontextmanager

import pytest
import sqlalchemy as sa

from middlewared.pytest.unit.datastore_harness import Model, datastore_test
from middlewared.service import CRUDService
from middlewared.utils.filter_list import select_with_query_fields


class ExtendContextTestModel(Model):
    __tablename__ = "test_extend_context"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String())


class ExtendContextTestService(CRUDService):
    class Config:
        private = True
        namespace = "test.extend_context"
        datastore = "test.extend_context"
        datastore_extend = "test.extend_context.extend"
        datastore_extend_context = "test.extend_context.extend_context"

    contexts: list
    extended: list

    async def extend_context(self, rows, extra):
        self.contexts.append({"rows": len(rows), "extra": extra})
        select = extra.get("select")
        return {"expensive": not select or "expensive" in select}

    async def extend(self, data, context):
        self.extended.append(data["id"])
        data["expensive"] = data["id"] * 10 if context["expensive"] else None
        return data


@asynccontextmanager
async def crud_test():
    async with datastore_test() as ds:
        m = ds.middleware
        for i, name in enumerate(["charlie", "alice", "bob"], start=1):
            await ds.insert("test.extend_context", {"id": i, "name": name})

        service = ExtendContextTestService(m)
        service.contexts = []
        service.extended = []
        m["test.extend_context.query"] = service.query
        m["test.extend_context.extend"] = service.extend
        m["test.extend_context.extend_context"] = service.extend_context

        yield service


@pytest.mark.asyncio
async def test__get_instance_extends_only_the_matching_row():
    async with crud_test() as service:
        assert await service.get_instance(2) == {"id": 2, "name": "alice", "expensive": 20}
        assert service.extended == [2]
        assert service.contexts[0]["rows"] == 1


@pytest.mark.asyncio
async def test__query_forwards_select_to_extend_context():
    async with crud_test() as service:
        assert await service.query([], {"select": ["id"]}) == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert service.contexts[0]["extra"]["select"] == ["id"]


@pytest.mark.asyncio
async def test__query_computes_fields_that_filters_read():
    async with crud_test() as service:
        assert await service.query([["expensive", "=", 20]], {"select": ["id"]}) == [{"id": 2}]


@pytest.mark.parametrize(
    "filters,options,fields",
    [
        ([["locked", "=", True]], {}, []),
        ([["locked", "=", True]], {"select": ["id"]}, ["id", "locked"]),
        (
            [["OR", [["purpose", "=", "X"], ["options.timemachine", "=", True]]]],
            {"select": [["name", "share_name"]]},
            [["name", "share_name"], "purpose", "options"],
        ),
        (
            [["OR", [[["a", "=", 1], ["b", "=", 2]], ["c", "=", 3]]]],
            {"select": ["id"]},
            ["id", "a", "b", "c"],
        ),
    ],
)
def test__select_with_query_fields(filters, options, fields):
    assert select_with_query_fields(filters, options) == fields
