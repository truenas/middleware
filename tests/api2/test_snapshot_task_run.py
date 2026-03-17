import time

import pytest

from middlewared.test.integration.assets.pool import dataset
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


def test_snapshot_task_run_success():
    with dataset("snaprun") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.snapshottask.run", task["id"], job=True)

            snapshots = call("pool.snapshot.query", [["dataset", "=", ds]])
            assert len(snapshots) == 1


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
