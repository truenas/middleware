import errno
import pprint
import pytest

from unittest.mock import ANY

from middlewared.service_exception import InstanceNotFound, ValidationErrors, ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import client

pytestmark = pytest.mark.zfs


def test_create():
    with dataset("test_snapshot_events_create") as ds:
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
    with dataset("test_snapshot_events_delete") as ds:
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


def test_delete_with_dependent_clone():
    with dataset("test_snapshot_events_dependent_clone") as ds:
        with client() as c:
            c.call("zfs.snapshot.create", {"dataset": ds, "name": "test"})
            c.call("zfs.snapshot.clone", {"snapshot": f"{ds}@test", "dataset_dst": f"{ds}/clone01"})

            with pytest.raises(ValidationErrors) as ve:
                c.call("zfs.snapshot.delete", f"{ds}@test")

            assert ve.value.errors == [
                ValidationError(
                    "options.defer",
                    f"Please set this attribute as '{ds}@test' snapshot has dependent clones: {ds}/clone01",
                    errno.EINVAL
                ),
            ]


def test_delete_nonexistent_snapshot():
    with dataset("test_snapshot_events_nonexistent_snapshot") as ds:
        with client() as c:
            c.call("zfs.snapshot.create", {"dataset": ds, "name": "test"})

            with pytest.raises(InstanceNotFound) as e:
                c.call("zfs.snapshot.delete", f"{ds}@testing")

            assert str(e.value) == f"[ENOENT] None: Snapshot {ds}@testing not found"
