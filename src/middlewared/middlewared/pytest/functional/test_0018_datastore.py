
def test_datastore_dump(conn):
    dump = conn.ws.call('datastore.dump')
    assert isinstance(dump, list) is True


def test_datastore_restore(conn):
    dump = conn.ws.call('datastore.dump')
    restore = conn.ws.call('datastore.restore', dump)
    assert restore is True
