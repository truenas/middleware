import pytest
from pytest_dependency import depends
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, mock
from time import sleep


DATASET_NAME = "snapshot_count"
NUM_SNAPSHOTS = 10


def test_snapshot_total_count_alert(request):
    with dataset(DATASET_NAME) as ds:
        base = call("zfs.snapshot.query", [], {"count": True})
        with mock("pool.snapshottask.max_total_count", return_value=base + NUM_SNAPSHOTS):
            for i in range(NUM_SNAPSHOTS):
                call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{i}"})

            assert call("alert.run_source", "SnapshotCount") == []
            # snapshots_changed ZFS dataset property has 1 second resolution
            sleep(1)

            call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{NUM_SNAPSHOTS}"})

            alert = call("alert.run_source", "SnapshotCount")[0]
            assert alert["text"] % alert["args"] == (
                f"Your system has more snapshots ({base + NUM_SNAPSHOTS + 1}) than recommended ({base + NUM_SNAPSHOTS}"
                "). Performance or functionality might degrade."
            )


def test_snapshot_count_alert(request):
    with (
        dataset(DATASET_NAME) as ds,
        smb_share(f"/mnt/{ds}", DATASET_NAME),
        mock("pool.snapshottask.max_count", return_value=NUM_SNAPSHOTS)
    ):
            for i in range(NUM_SNAPSHOTS):
                call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{i}"})

            assert call("alert.run_source", "SnapshotCount") == []
            # snapshots_changed ZFS dataset property has 1 second resolution
            sleep(1)

            call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{NUM_SNAPSHOTS}"})

            alert = call("alert.run_source", "SnapshotCount")[0]
            assert alert["text"] % alert["args"] == (
                f"SMB share {ds} has more snapshots ({NUM_SNAPSHOTS + 1}) than recommended ({NUM_SNAPSHOTS}). File "
                "Explorer may not display all snapshots in the Previous Versions tab."
            )
