from unittest.mock import ANY

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


def test_normal_snapshot():
    with dataset("test") as ds:
        with snapshot(ds, "test") as id:
            assert call("zfs.snapshot.get_instance", id, {"extra": {"holds": True}})["holds"] == {}


def test_held_snapshot():
    with dataset("test") as ds:
        with snapshot(ds, "test") as id:
            call("zfs.snapshot.hold", id)

            assert call("zfs.snapshot.get_instance", id, {"extra": {"holds": True}})["holds"] == {"truenas": ANY}

            call("zfs.snapshot.release", id)  # Otherwise the whole test tree won't be deleted


def test_held_snapshot_tree():
    with dataset("test") as ds:
        with dataset("test/child") as ds2:
            with snapshot(ds, "test", recursive=True) as id:
                id2 = f"{ds2}@test"

                call("zfs.snapshot.hold", id, {"recursive": True})

                assert call("zfs.snapshot.get_instance", id, {"extra": {"holds": True}})["holds"] == {"truenas": ANY}
                assert call("zfs.snapshot.get_instance", id2, {"extra": {"holds": True}})["holds"] == {"truenas": ANY}

                call("zfs.snapshot.release", id, {"recursive": True})  # Otherwise the whole test tree won't be deleted
