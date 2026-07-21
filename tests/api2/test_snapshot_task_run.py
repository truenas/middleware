import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call

TASK_DATA = {
    "recursive": False,
    "lifetime_value": 1,
    "lifetime_unit": "DAY",
    "naming_schema": "auto-%Y-%m-%d_%H-%M",
    "schedule": {
        "minute": "0",
        "hour": "0",
        "dom": "1",
        "month": "1",
        "dow": "1",
    },
    "enabled": True,
}


def test_max_count():
    assert call("pool.snapshottask.max_count") == 512


def test_max_total_count():
    assert call("pool.snapshottask.max_total_count") == 10000


def test_snapshot_task_run_success():
    with dataset("snaprun") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.snapshottask.run", task["id"], job=True)

            snapshots = call("pool.snapshot.query", [["dataset", "=", ds]])
            assert len(snapshots) == 1

            # Running the task pushes a `periodic_snapshot_task_*` zettarepl state change, which the
            # `zettarepl.state_change` hook turns into a `pool.snapshottask.query` CHANGED event.
            assert call("pool.snapshottask.get_instance", task["id"])["state"]["state"] == "FINISHED"


def test_snapshot_task_run_already_existed():
    with dataset("snaprun_dup") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            # First manual run creates the snapshot
            call("pool.snapshottask.run", task["id"], job=True)

            # Second manual run within the same minute produces the same snapshot name and hits "already existed"
            with pytest.raises(Exception, match="already existed.*ran on schedule"):
                call("pool.snapshottask.run", task["id"], job=True)

            # This error should not affect the snapshot task status
            state = call("pool.snapshottask.get_instance", task["id"])["state"]
            assert state["state"] == "FINISHED"


def test_snapshot_task_run_error():
    with dataset("snaprun_err") as ds:
        pool = ds.split("/")[0]
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("datastore.update", "storage.task", task["id"], {"task_dataset": f"{pool}/nonexistent_dataset"})
            call("zettarepl.update_tasks")
            with pytest.raises(Exception):
                call("pool.snapshottask.run", task["id"], job=True)


def test_snapshot_task_run_disabled_task_raises():
    """Running a disabled periodic snapshot task should raise a CallError, not crash."""
    with dataset("snap_disabled") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds, "enabled": False}) as task:
            with pytest.raises(ClientException, match="Task is not enabled"):
                call("pool.snapshottask.run", task["id"], job=True)


def test_zettarepl_state_change_for_a_non_snapshot_task():
    """Non-snapshot zettarepl state changes pass through the hook without being republished."""
    with dataset("snaprun_repl_src") as src, dataset("snaprun_repl_dst") as dst:
        call("pool.snapshot.create", {"dataset": src, "name": "manual-1"})

        with replication_task(
            {
                "name": "snaprun_state_change",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": f"{dst}/target",
                "recursive": False,
                "name_regex": ".+",
                "auto": False,
                "retention_policy": "NONE",
            }
        ) as task:
            call("replication.run", task["id"], job=True)

            assert call("replication.get_instance", task["id"])["state"]["state"] == "FINISHED"
