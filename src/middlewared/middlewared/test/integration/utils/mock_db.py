# -*- coding=utf-8 -*-
import contextlib

from .call import call


@contextlib.contextmanager
def mock_table_contents(name, rows):
    old_rows = call("datastore.query", name, [], {"relationships": False})
    call("datastore.delete", name, [])
    try:
        for row in rows:
            call("datastore.insert", name, row)

        yield
    finally:
        call("datastore.delete", name, [])
        for row in old_rows:
            call("datastore.insert", name, row)
