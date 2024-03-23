import pytest
from pytest_dependency import depends
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock
from time import sleep

pytestmark = [pytest.mark.alerts, pytest.mark.zfs]

def test_snapshot_total_count_alert(request):
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
