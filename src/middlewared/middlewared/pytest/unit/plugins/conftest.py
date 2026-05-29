from contextlib import asynccontextmanager
from unittest.mock import patch

from sqlalchemy.ext.declarative import declarative_base

from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware

DatastoreService = load_compound_service("datastore")

# Shared declarative base for datastore-backed unit tests. Test modules register their tables on
# this base; `datastore_test` patches the datastore service to use it and creates the tables.
Model = declarative_base()


@asynccontextmanager
async def datastore_test(mocked_calls=None):
    mocked_calls = mocked_calls or {}
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
        m["datastore.send_insert_events"] = ds.send_insert_events
        m["datastore.send_update_events"] = ds.send_update_events
        m["datastore.send_delete_events"] = ds.send_delete_events

        m["datastore.insert"] = ds.insert
        m["datastore.update"] = ds.update
        m["datastore.delete"] = ds.delete

        for call_name, call_func in mocked_calls.items():
            m[call_name] = call_func

        yield ds
