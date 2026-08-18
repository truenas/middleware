from contextlib import asynccontextmanager
from unittest.mock import patch

from sqlalchemy.ext.declarative import declarative_base

from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware

DatastoreService = load_compound_service("datastore")

# Shared declarative base for datastore-backed unit tests. Test modules register their tables on
# this base; `datastore_test` patches the datastore service to use it and creates the tables.
Model = declarative_base()


#: The classes `_rebind_model` created, keyed by table name. SQLAlchemy's class registry only holds
#: them weakly, so without this they would be collected again as soon as the caller drops them.
_rebound_models = {}


def _rebind_model(model):
    """Map a production model onto the test `Model` base and return the mapped class.

    The datastore service looks its tables up on whatever base `datastore_test` patched in, so a
    production table is invisible to it. Copying the real table over instead of redeclaring it in
    the test keeps the two from drifting apart. Repeated calls return the class from the first one.

    `relationship()` definitions are *not* carried over, so `datastore.query` will not expand the
    related rows of a rebound model. A test that needs them has to declare its own model instead.
    """
    if (rebound := _rebound_models.get(model.__tablename__)) is None:
        # The class registry is keyed by class name, and a name a test module also uses would
        # collapse both entries into a marker object that the datastore cannot look a table up by.
        name = f"Rebound_{model.__tablename__}"
        # `type()` would bypass the declarative metaclass, leaving the class unmapped.
        rebound = _rebound_models[model.__tablename__] = type(Model)(name, (Model,), {
            "__tablename__": model.__tablename__,
            "__table__": model.__table__.to_metadata(Model.metadata),
        })

    return rebound


@asynccontextmanager
async def datastore_test(mocked_calls=None, models=()):
    """Set up an in-memory datastore holding the tables declared on `Model`, plus `models`.

    `models` are production models, rebound onto the test base so that the test runs against the
    real table instead of a copy that has to be kept in step by hand. A model with a foreign key can
    only be rebound together with the models it points at, as the referenced table has to exist.
    """
    mocked_calls = mocked_calls or {}
    for model in models:
        _rebind_model(model)

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
