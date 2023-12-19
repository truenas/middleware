import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def row(datastore, data, options=None):
    options = options or {}

    id_ = call("datastore.insert", datastore, data, options)
    try:
        yield id_
    finally:
        call("datastore.delete", datastore, id_)
