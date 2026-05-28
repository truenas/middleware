from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import CRUDService

DatastoreService = load_compound_service("datastore")

Model = declarative_base()


class CRUDTestModel(Model):
    __tablename__ = 'test_crud'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String())
    priority = sa.Column(sa.Integer())


class CRUDTestService(CRUDService):
    class Config:
        private = True
        datastore = 'test.crud'
        datastore_extend = 'test.crud.extend'

    async def extend(self, data):
        # `score` only exists on the extended result, never as a SQL column. Ordering by it
        # used to raise KeyError in the datastore layer (NAS regression).
        data['score'] = 100 - data['priority']
        return data


# Rows chosen so DB order (id), `priority`, `name`, and the extend-only `score` all disagree.
ROWS = [
    {'id': 1, 'name': 'charlie', 'priority': 10},  # score 90
    {'id': 2, 'name': 'alice', 'priority': 30},    # score 70
    {'id': 3, 'name': 'bob', 'priority': 20},      # score 80
]


@asynccontextmanager
async def crud_test():
    m = Middleware()
    with (
        patch("middlewared.plugins.datastore.connection.FREENAS_DATABASE", ":memory:"),
        patch("middlewared.plugins.datastore.schema.Model", Model),
        patch("middlewared.plugins.datastore.util.Model", Model),
    ):
        ds = DatastoreService(m)
        ds.setup()

        for part in ds.parts:
            if hasattr(part, "connection"):
                Model.metadata.create_all(bind=part.connection)
                break
        else:
            raise RuntimeError("Could not find part that provides connection")

        m["datastore.execute"] = ds.execute
        m["datastore.execute_write"] = ds.execute_write
        m["datastore.fetchall"] = ds.fetchall
        m["datastore.query"] = ds.query
        m["datastore.insert"] = ds.insert
        m["datastore.send_insert_events"] = ds.send_insert_events

        for row in ROWS:
            await ds.insert('test.crud', dict(row))

        service = CRUDTestService(m)
        m["test.crud.extend"] = service.extend

        yield service


@pytest.mark.asyncio
@pytest.mark.parametrize("order_by,ids", [
    # extend-only field: the regression case (previously raised KeyError)
    (["score"], [2, 3, 1]),
    (["-score"], [1, 3, 2]),
    # real columns must still order correctly with an extend method configured
    (["priority"], [1, 3, 2]),
    (["-priority"], [2, 3, 1]),
    (["name"], [2, 3, 1]),
    (["id"], [1, 2, 3]),
])
async def test__crud_query_order_by_with_extend(order_by, ids):
    async with crud_test() as service:
        result = await service.query([], {"order_by": order_by})
        assert [row["id"] for row in result] == ids
        # extend is always applied, regardless of what we order by
        assert all("score" in row for row in result)


@pytest.mark.asyncio
async def test__crud_query_order_by_extend_field_with_pagination():
    # order_by an extend field combined with limit/offset (all applied by filter_list)
    async with crud_test() as service:
        result = await service.query([], {"order_by": ["score"], "limit": 2})
        assert [row["id"] for row in result] == [2, 3]
