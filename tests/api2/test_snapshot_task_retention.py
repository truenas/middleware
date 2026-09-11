import errno
from datetime import datetime
from unittest.mock import ANY
from zoneinfo import ZoneInfo

import pytest

from middlewared.service_exception import CallError, InstanceNotFound
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import assert_creates_job, call, mock, ssh

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


def test_load_removal_dates():
    """`zettarepl.load_removal_dates` picks up valid removal dates and skips unparseable ones."""
    property_name = call("pool.snapshottask.removal_date_property")
    with dataset("retention-load") as ds:
        call("pool.snapshot.create", {"dataset": ds, "name": "good"})
        call("pool.snapshot.create", {"dataset": ds, "name": "bad"})
        ssh(f"zfs set {property_name}=2030-01-01T00:00:00 {ds}@good")
        ssh(f"zfs set {property_name}=not-a-date {ds}@bad")

        call("zettarepl.load_removal_dates")
        removal_dates = call("zettarepl.get_removal_dates")
        assert f"{ds}@good" in removal_dates
        assert f"{ds}@bad" not in removal_dates

        # Reloading a single pool keeps the other pools' dates and refreshes this pool's.
        call("zettarepl.load_removal_dates", ds.split("/")[0])
        removal_dates = call("zettarepl.get_removal_dates")
        assert f"{ds}@good" in removal_dates


def test_fixate_removal_date_does_not_shorten_existing_retention():
    """Fixating a shorter lifetime does not overwrite an already fixated later removal date."""
    tz = ZoneInfo(call("system.info")["timezone"])
    snapshot = "auto-2021-04-12-06-30-1y"

    with dataset("retention-keep-later") as ds:
        call("zettarepl.load_removal_dates")

        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:  # 10 YEAR lifetime
            call("pool.snapshot.create", {"dataset": ds, "name": snapshot})

            with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
                call("pool.snapshottask.delete", task["id"], {"fixate_removal_date": True})

            call("core.job_wait", job.id, job=True)

        with snapshot_task({**TASK_DATA, "dataset": ds, "lifetime_value": 1, "lifetime_unit": "DAY"}) as task:
            with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
                call("pool.snapshottask.delete", task["id"], {"fixate_removal_date": True})

            call("core.job_wait", job.id, job=True)

        # The 10 year removal date must have survived the 1 day fixation attempt.
        result = call(
            "pool.snapshot.query",
            [["id", "=", f"{ds}@{snapshot}"]],
            {"get": True, "extra": {"retention": True}},
        )
        assert result["retention"]["source"] == "property"
        assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)


def test_annotate_snapshots_property_and_task_interaction():
    """When a snapshot has both a task retention and a removal date property, the later one wins."""
    property_name = call("pool.snapshottask.removal_date_property")
    snapshot = "auto-2021-04-12-06-30-1y"

    with dataset("retention-both") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:  # 10 YEAR lifetime
            call("pool.snapshot.create", {"dataset": ds, "name": snapshot})

            def query_retention():
                return call(
                    "pool.snapshot.query",
                    [["id", "=", f"{ds}@{snapshot}"]],
                    {"get": True, "extra": {"retention": True}},
                )["retention"]

            # The property removal date is earlier than the task retention, so the task wins.
            ssh(f"zfs set {property_name}=2022-01-01T00:00:00 {ds}@{snapshot}")
            retention = query_retention()
            assert retention["source"] == "periodic_snapshot_task"
            assert retention["periodic_snapshot_task_id"] == task["id"]

            # The property removal date is later than the task retention, so the property wins.
            ssh(f"zfs set {property_name}=2099-01-01T00:00:00 {ds}@{snapshot}")
            assert query_retention()["source"] == "property"

            # An unparseable property value is ignored and the task retention is used.
            ssh(f"zfs set {property_name}=not-a-date {ds}@{snapshot}")
            assert query_retention()["source"] == "periodic_snapshot_task"


def test_annotate_snapshots_no_retention():
    """A snapshot that no task owns and that has no removal date property has no retention."""
    with dataset("retention-none") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}):
            call("pool.snapshot.create", {"dataset": ds, "name": "manual-1"})

            result = call(
                "pool.snapshot.query",
                [["id", "=", f"{ds}@manual-1"]],
                {"get": True, "extra": {"retention": True}},
            )
            assert result["retention"] is None


def test_task_snapshot_ownership_edge_cases():
    """Snapshots on excluded datasets or outside the task schedule are not owned by the task."""
    owned = "auto-2021-01-01-00-00-1y"
    off_schedule = "auto-2021-04-12-06-30-1y"

    with dataset("retention-own") as ds:
        with dataset("retention-own/excluded") as excluded:
            with snapshot_task({
                **TASK_DATA,
                "dataset": ds,
                "exclude": [excluded],
                # Only January 1st, 00:00
                "schedule": {"minute": "0", "hour": "0", "dom": "1", "month": "1"},
            }) as task:
                call("pool.snapshot.create", {"dataset": ds, "name": owned})
                call("pool.snapshot.create", {"dataset": ds, "name": off_schedule})
                call("pool.snapshot.create", {"dataset": excluded, "name": owned})

                assert call("pool.snapshottask.delete_will_change_retention_for", task["id"]) == {
                    ds: [owned],
                }

                for snapshot_id in (f"{ds}@{off_schedule}", f"{excluded}@{owned}"):
                    result = call(
                        "pool.snapshot.query",
                        [["id", "=", snapshot_id]],
                        {"get": True, "extra": {"retention": True}},
                    )
                    assert result["retention"] is None, snapshot_id


def test_annotate_snapshots_multiple_owning_tasks():
    """When several tasks own a snapshot, the longest retention (and its task id) is reported."""
    snapshot = "auto-2021-04-12-06-30-1y"

    with dataset("retention-multi-owner") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as long_task:  # 10 YEAR lifetime
            with snapshot_task({**TASK_DATA, "dataset": ds, "lifetime_value": 1, "lifetime_unit": "DAY"}):
                call("pool.snapshot.create", {"dataset": ds, "name": snapshot})

                result = call(
                    "pool.snapshot.query",
                    [["id", "=", f"{ds}@{snapshot}"]],
                    {"get": True, "extra": {"retention": True}},
                )
                assert result["retention"]["source"] == "periodic_snapshot_task"
                assert result["retention"]["periodic_snapshot_task_id"] == long_task["id"]
