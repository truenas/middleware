import pprint
from unittest.mock import ANY

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import client


def test_create():
    with dataset("test") as ds:
        with client() as c:
            events = []

            def callback(type, **message):
                events.append((type, message))

            c.subscribe("zfs.snapshot.query", callback, sync=True)
            c.call("zfs.snapshot.create", {"dataset": ds, "name": "test"})

            assert len(events) == 1, pprint.pformat(events, indent=2)
            assert events[0][0] == "ADDED"
            assert events[0][1] == {"collection": "zfs.snapshot.query", "msg": "added", "id": f"{ds}@test",
                                    "fields": ANY}


def test_delete():
    with dataset("test") as ds:
        with client() as c:
            c.call("zfs.snapshot.create", {"dataset": ds, "name": "test"})

            events = []

            def callback(type, **message):
                events.append((type, message))

            c.subscribe("zfs.snapshot.query", callback, sync=True)
            c.call("zfs.snapshot.delete", f"{ds}@test")

            assert len(events) == 1, pprint.pformat(events, indent=2)
            assert events[0][0] == "REMOVED"
            assert events[0][1] == {"collection": "zfs.snapshot.query", "msg": "removed", "id": f"{ds}@test",
                                    "extra": {"recursive": False}}
