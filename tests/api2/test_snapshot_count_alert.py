import pytest
from pytest_dependency import depends
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock
from auto_config import dev_test, pool_name
from time import sleep
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test_snapshot_total_count_alert(request):
    depends(request, [pool_name], scope="session")
    with dataset("snapshot_count") as ds:
        base = call("zfs.snapshot.query", [], {"count": True})
        with mock("pool.snapshottask.max_total_count", return_value=base + 10):
            for i in range(10):
                call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{i}"})

            assert call("alert.run_source", "SnapshotCount") == []
            # snapshots_changed ZFS dataset property has 1 second resolution
            sleep(1)

            call("zfs.snapshot.create", {"dataset": ds, "name": "snap-10"})

            alert = call("alert.run_source", "SnapshotCount")[0]
            assert alert["text"] % alert["args"] == (
                f"Your system has more snapshots ({base + 11}) than recommended ({base + 10}). Performance or "
                "functionality might degrade."
            )


def test_snapshot_count_alert(request):
    depends(request, [pool_name], scope="session")
    with dataset("snapshot_count") as ds:
        with mock("pool.snapshottask.max_count", return_value=10):
            for i in range(10):
                call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{i}"})

            assert call("alert.run_source", "SnapshotCount") == []
            # snapshots_changed ZFS dataset property has 1 second resolution
            sleep(1)

            call("zfs.snapshot.create", {"dataset": ds, "name": "snap-10"})

            alert = call("alert.run_source", "SnapshotCount")[0]
            assert alert["text"] % alert["args"] == (
                "Dataset tank/snapshot_count has more snapshots (11) than recommended (10). Performance or "
                "functionality might degrade."
            )
