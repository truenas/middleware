from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock


def test_snapshot_count_alert():
    with dataset("snapshot_count") as ds:
        with mock("pool.snapshottask.max_count", return_value=10):
            for i in range(10):
                call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{i}"})

            assert call("alert.run_source", "SnapshotCount") == []

            call("zfs.snapshot.create", {"dataset": ds, "name": "snap-10"})

            alert = call("alert.run_source", "SnapshotCount")[0]
            assert alert["text"] % alert["args"] == (
                "Dataset tank/snapshot_count has more snapshots (11) than recommended (10). Performance or "
                "functionality might degrade."
            )
