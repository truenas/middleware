import errno

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


def test_pool_snapshot_rollback_recursive():
    """Options are passed through: `recursive` destroys the newer snapshot and the rollback succeeds"""
    with dataset("test_pool_snap_rollback") as ds:
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            call("pool.snapshot.rollback", f"{ds}@snap1", {"recursive": True})

            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]


def test_pool_snapshot_rollback_input_errors_are_validation_errors():
    """The wrapper translates the input problems of the underlying rollback into its own schema"""
    with dataset("test_pool_snap_rollback_errors") as ds:
        with pytest.raises(ValidationError) as ve:
            call("pool.snapshot.rollback", ds)
        assert ve.value.errno == errno.EINVAL
        assert "must be a snapshot path" in ve.value.errmsg

        with pytest.raises(ValidationError) as ve:
            call("pool.snapshot.rollback", f"{ds}@nonexistent")
        assert ve.value.errno == errno.ENOENT
        assert ve.value.errmsg == f"'{ds}@nonexistent' not found"

        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            with pytest.raises(ValidationError) as ve:
                call("pool.snapshot.rollback", f"{ds}@snap1")
            assert ve.value.errno == errno.EINVAL
            assert "more recent snapshots exist" in ve.value.errmsg
            assert f"{ds}@snap2" in ve.value.errmsg
