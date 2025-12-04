import pprint
import pytest

from unittest.mock import ANY

from middlewared.service_exception import InstanceNotFound, ValidationErrors, ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import client


def test_create():
    with dataset("test_snapshot_events_create") as ds:
        with client() as c:
            events = []

            def callback(type, **message):
                events.append((type, message))

            c.subscribe("pool.snapshot.query", callback, sync=True)
            c.call("pool.snapshot.create", {"dataset": ds, "name": "test"})

            assert len(events) == 1, pprint.pformat(events, indent=2)
            assert events[0][0] == "ADDED"
            assert events[0][1] == {"collection": "pool.snapshot.query", "msg": "added", "id": f"{ds}@test",
                                    "fields": ANY}


def test_delete():
    with dataset("test_snapshot_events_delete") as ds:
        with client() as c:
            c.call("pool.snapshot.create", {"dataset": ds, "name": "test"})

            events = []

            def callback(type, **message):
                events.append((type, message))

            c.subscribe("pool.snapshot.query", callback, sync=True)
            c.call("pool.snapshot.delete", f"{ds}@test")

            assert len(events) == 1, pprint.pformat(events, indent=2)
            assert events[0][0] == "REMOVED"
            assert events[0][1] == {"collection": "pool.snapshot.query", "msg": "removed", "id": f"{ds}@test",
                                    "extra": {"recursive": False}}


def test_delete_with_dependent_clone():
    with dataset("test_snapshot_events_dependent_clone") as ds:
        with client() as c:
            c.call("pool.snapshot.create", {"dataset": ds, "name": "test"})
            c.call("pool.snapshot.clone", {"snapshot": f"{ds}@test", "dataset_dst": f"{ds}/clone01"})

            with pytest.raises(ValidationError) as ve:
                c.call("pool.snapshot.delete", f"{ds}@test")

            assert ve.value.attribute == "zfs.resource.destroy.defer"
            assert ve.value.errmsg == f"Snapshot '{ds}@test' has dependent clones: {ds}/clone01"

            c.call("pool.snapshot.delete", f"{ds}@test", {"defer": True})
            c.call("pool.snapshot.get_instance", f"{ds}@test")

            c.call("pool.dataset.delete", f"{ds}/clone01")
            with pytest.raises(InstanceNotFound):
                c.call("pool.snapshot.get_instance", f"{ds}@test")


def test_recursive_delete_with_dependent_clone():
    with dataset("test_snapshot_events_dependent_clone") as ds:
        with client() as c:
            c.call("pool.dataset.create", {"name": f"{ds}/child"})
            c.call("pool.snapshot.create", {"dataset": ds, "name": "test", "recursive": True})
            c.call("pool.snapshot.clone", {"snapshot": f"{ds}@test", "dataset_dst": f"{ds}/clone01"})
            c.call("pool.snapshot.clone", {"snapshot": f"{ds}/child@test", "dataset_dst": f"{ds}/clone02"})

            with pytest.raises(ValidationErrors):
                c.call("pool.snapshot.delete", f"{ds}@test")

            c.call("pool.snapshot.delete", f"{ds}@test", {"recursive": True})
            with pytest.raises(InstanceNotFound):
                c.call("pool.snapshot.get_instance", f"{ds}@test")
            with pytest.raises(InstanceNotFound):
                c.call("pool.snapshot.get_instance", f"{ds}/child@test")


def test_delete_nonexistent_snapshot():
    with dataset("test_snapshot_events_nonexistent_snapshot") as ds:
        with client() as c:
            c.call("pool.snapshot.create", {"dataset": ds, "name": "test"})

            with pytest.raises(InstanceNotFound) as e:
                c.call("pool.snapshot.delete", f"{ds}@testing")

            assert str(e.value) == f"[ENOENT] None: '{ds}@testing' not found"
