import errno
from datetime import datetime
from unittest.mock import ANY
from zoneinfo import ZoneInfo

import pytest

from middlewared.service_exception import CallError, InstanceNotFound
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import assert_creates_job, call, mock

TASK_DATA = {
    "recursive": True,
    "exclude": [],
    "lifetime_value": 10,
    "lifetime_unit": "YEAR",
    "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
    "schedule": {
        "minute": "*",
    },
}
RAISE_UNEXPECTED_CALL_ERROR = """\
    def mock(self, task):
        import errno
        from middlewared.service_exception import CallError
        raise CallError("Unexpected zettarepl failure", errno.EINVAL)
"""


def test_change_retention():
    tz = ZoneInfo(call("system.info")["timezone"])

    with dataset("snapshottask-retention-test") as ds:
        call("zettarepl.load_removal_dates")

        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call(
                "pool.snapshot.create",
                {
                    "dataset": ds,
                    "name": "auto-2021-04-12-06-30-1y",
                },
            )

            result = call(
                "pool.snapshot.query",
                [["id", "=", f"{ds}@auto-2021-04-12-06-30-1y"]],
                {"get": True, "extra": {"retention": True}},
            )
            assert result["retention"] == {
                "datetime": ANY,
                "source": "periodic_snapshot_task",
                "periodic_snapshot_task_id": task["id"],
            }
            assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)

            result = call(
                "pool.snapshottask.update_will_change_retention_for",
                task["id"],
                {
                    "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
                },
            )
            assert result == {
                ds: ["auto-2021-04-12-06-30-1y"],
            }

            with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
                call(
                    "pool.snapshottask.update",
                    task["id"],
                    {
                        "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
                        "fixate_removal_date": True,
                    },
                )

            call("core.job_wait", job.id, job=True)

            result = call(
                "pool.snapshot.query",
                [["id", "=", f"{ds}@auto-2021-04-12-06-30-1y"]],
                {"get": True, "extra": {"retention": True}},
            )
            assert result["retention"] == {
                "datetime": ANY,
                "source": "property",
            }
            assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)


def test_delete_retention():
    tz = ZoneInfo(call("system.info")["timezone"])

    with dataset("snapshottask-retention-test-2") as ds:
        call("zettarepl.load_removal_dates")

        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call(
                "pool.snapshot.create",
                {
                    "dataset": ds,
                    "name": "auto-2021-04-12-06-30-1y",
                },
            )

            result = call("pool.snapshottask.delete_will_change_retention_for", task["id"])
            assert result == {
                ds: ["auto-2021-04-12-06-30-1y"],
            }

            with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
                call(
                    "pool.snapshottask.delete",
                    task["id"],
                    {
                        "fixate_removal_date": True,
                    },
                )

            call("core.job_wait", job.id, job=True)

            result = call(
                "pool.snapshot.query",
                [["id", "=", f"{ds}@auto-2021-04-12-06-30-1y"]],
                {"get": True, "extra": {"retention": True}},
            )
            assert result["retention"] == {
                "datetime": ANY,
                "source": "property",
            }
            assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)


def test_update_will_change_retention_for_no_change():
    """An update that does not actually change the task can't change any snapshot's retention."""
    with dataset("snapshottask-retention-nochange") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.snapshot.create", {"dataset": ds, "name": "auto-2021-04-12-06-30-1y"})

            assert (
                call(
                    "pool.snapshottask.update_will_change_retention_for",
                    task["id"],
                    {
                        "naming_schema": TASK_DATA["naming_schema"],
                    },
                )
                == {}
            )


def test_update_will_change_retention_for_no_snapshots_lost():
    """Changing the lifetime keeps the same set of owned snapshots, so nothing changes retention."""
    with dataset("snapshottask-retention-nodiff") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.snapshot.create", {"dataset": ds, "name": "auto-2021-04-12-06-30-1y"})

            assert (
                call(
                    "pool.snapshottask.update_will_change_retention_for",
                    task["id"],
                    {
                        "lifetime_value": 20,
                    },
                )
                == {}
            )


def test_update_will_change_retention_for_missing_dataset():
    """A task whose dataset no longer exists reports no retention changes instead of failing."""
    with dataset("snapshottask-retention-gone") as ds:
        renamed = ds.rsplit("/", 1)[0] + "/snapshottask-retention-renamed"
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.dataset.rename", ds, {"new_name": renamed, "force": True})
            try:
                assert (
                    call(
                        "pool.snapshottask.update_will_change_retention_for",
                        task["id"],
                        {
                            "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
                        },
                    )
                    == {}
                )
            finally:
                call("pool.dataset.delete", renamed, {"recursive": True})


def test_update_will_change_retention_for_unexpected_error():
    """Errors other than `ENOENT` are propagated to the caller."""
    with dataset("snapshottask-retention-error") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with mock("zettarepl.periodic_snapshot_task_snapshots", RAISE_UNEXPECTED_CALL_ERROR):
                with pytest.raises(CallError) as ce:
                    call(
                        "pool.snapshottask.update_will_change_retention_for",
                        task["id"],
                        {
                            "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
                        },
                    )

            assert ce.value.errno == errno.EINVAL


def test_delete_will_change_retention_for_missing_dataset():
    """`delete_will_change_retention_for` tolerates a task whose dataset was renamed away."""
    with dataset("snapshottask-retention-del-gone") as ds:
        renamed = ds.rsplit("/", 1)[0] + "/snapshottask-retention-del-renamed"
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.dataset.rename", ds, {"new_name": renamed, "force": True})
            try:
                assert call("pool.snapshottask.delete_will_change_retention_for", task["id"]) == {}
            finally:
                call("pool.dataset.delete", renamed, {"recursive": True})


def test_delete_will_change_retention_for_unexpected_error():
    with dataset("snapshottask-retention-del-error") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with mock("zettarepl.periodic_snapshot_task_snapshots", RAISE_UNEXPECTED_CALL_ERROR):
                with pytest.raises(CallError) as ce:
                    call("pool.snapshottask.delete_will_change_retention_for", task["id"])

            assert ce.value.errno == errno.EINVAL


def test_snapshot_task_can_be_deleted_after_dataset_rename():
    """Deleting a periodic snapshot task should succeed even if the dataset was renamed."""
    with dataset("snap_orig") as ds:
        renamed = ds.rsplit("/", 1)[0] + "/snap_renamed"
        with snapshot_task(
            {
                "dataset": ds,
                "recursive": True,
                "lifetime_value": 1,
                "lifetime_unit": "DAY",
                "naming_schema": "%Y%m%d%H%M",
            }
        ) as t:
            call("pool.dataset.rename", ds, {"new_name": renamed, "force": True})
            try:
                call("pool.snapshottask.delete", t["id"], {"fixate_removal_date": True})

                with pytest.raises(InstanceNotFound):
                    call("pool.snapshottask.get_instance", t["id"])
            finally:
                call("pool.dataset.delete", renamed, {"recursive": True})


def test_removal_date_property():
    host_id = call("system.host_id")
    assert call("pool.snapshottask.removal_date_property") == f"org.truenas:destroy_at_{host_id[:8]}"
