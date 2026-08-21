import errno

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, ssh


def test_pool_snapshot_rollback_recursive():
    """Rolling back with `recursive` destroys the newer snapshot and succeeds"""
    with dataset("test_pool_snap_rollback") as ds:
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            call("pool.snapshot.rollback", f"{ds}@snap1", {"recursive": True})

            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]


def test_pool_snapshot_rollback_nonexistent():
    with dataset("test_pool_snap_rollback_noent") as ds:
        with pytest.raises(ValidationError) as ve:
            call("pool.snapshot.rollback", f"{ds}@nonexistent")

        assert ve.value.errno == errno.ENOENT
        assert ve.value.errmsg == f"'{ds}@nonexistent' not found"


def test_pool_snapshot_rollback_not_a_snapshot():
    with dataset("test_pool_snap_rollback_not_snap") as ds:
        with pytest.raises(ValidationError) as ve:
            call("pool.snapshot.rollback", ds)

        assert ve.value.errno == errno.EINVAL
        assert "must be a snapshot path" in ve.value.errmsg


def test_pool_snapshot_rollback_newer_snapshots_without_flags():
    with dataset("test_pool_snap_rollback_newer") as ds:
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            with pytest.raises(ValidationError) as ve:
                call("pool.snapshot.rollback", f"{ds}@snap1")

            assert ve.value.errno == errno.EINVAL
            assert "more recent snapshots or bookmarks exist" in ve.value.errmsg
            assert f"{ds}@snap2" in ve.value.errmsg


def test_pool_snapshot_rollback_clone_blocks():
    with dataset("test_pool_snap_rollback_clone") as ds:
        # The clone lives under the dataset, so it is reaped by its recursive delete
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")

            with pytest.raises(ValidationError) as ve:
                call("pool.snapshot.rollback", f"{ds}@snap1", {"recursive": True})

            assert ve.value.errno == errno.EBUSY
            assert clone in ve.value.errmsg

            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert {snap["snapshot_name"] for snap in result} == {"snap1", "snap2"}


def test_pool_snapshot_rollback_recursive_clones():
    with dataset("test_pool_snap_rollback_clone_destroy") as ds:
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")

            call(
                "pool.snapshot.rollback",
                f"{ds}@snap1",
                {"recursive_clones": True, "force": True},
            )

            assert ssh(f"zfs list -H -o name {clone}", check=False, complete_response=True)["result"] is False
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]
