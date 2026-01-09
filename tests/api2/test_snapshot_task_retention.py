from datetime import datetime
from unittest.mock import ANY
from zoneinfo import ZoneInfo

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import assert_creates_job, call


def test_change_retention():
    tz = ZoneInfo(call("system.info")["timezone"])

    with dataset("snapshottask-retention-test") as ds:
        call("zettarepl.load_removal_dates")

        with snapshot_task({
            "dataset": ds,
            "recursive": True,
            "exclude": [],
            "lifetime_value": 10,
            "lifetime_unit": "YEAR",
            "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
            "schedule": {
                "minute": "*",
            },
        }) as task:
            call("pool.snapshot.create", {
                "dataset": ds,
                "name": "auto-2021-04-12-06-30-1y",
            })

            result = call("pool.snapshot.query", [["id", "=", f"{ds}@auto-2021-04-12-06-30-1y"]],
                          {"get": True, "extra": {"retention": True}})
            assert result["retention"] == {
                "datetime": ANY,
                "source": "periodic_snapshot_task",
                "periodic_snapshot_task_id": task["id"],
            }
            assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)

            result = call("pool.snapshottask.update_will_change_retention_for", task["id"], {
                "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
            })
            assert result == {
                ds: ["auto-2021-04-12-06-30-1y"],
            }

            with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
                call("pool.snapshottask.update", task["id"], {
                    "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
                    "fixate_removal_date": True,
                })

            call("core.job_wait", job.id, job=True)

            result = call("pool.snapshot.query", [["id", "=", f"{ds}@auto-2021-04-12-06-30-1y"]],
                          {"get": True, "extra": {"retention": True}})
            assert result["retention"] == {
                "datetime": ANY,
                "source": "property",
            }
            assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)


def test_delete_retention():
    tz = ZoneInfo(call("system.info")["timezone"])

    with dataset("snapshottask-retention-test-2") as ds:
        call("zettarepl.load_removal_dates")

        with snapshot_task({
            "dataset": ds,
            "recursive": True,
            "exclude": [],
            "lifetime_value": 10,
            "lifetime_unit": "YEAR",
            "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
            "schedule": {
                "minute": "*",
            },
        }) as task:
            call("pool.snapshot.create", {
                "dataset": ds,
                "name": "auto-2021-04-12-06-30-1y",
            })

            result = call("pool.snapshottask.delete_will_change_retention_for", task["id"])
            assert result == {
                ds: ["auto-2021-04-12-06-30-1y"],
            }

            with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
                call("pool.snapshottask.delete", task["id"], {
                    "fixate_removal_date": True,
                })

            call("core.job_wait", job.id, job=True)

            result = call("pool.snapshot.query", [["id", "=", f"{ds}@auto-2021-04-12-06-30-1y"]],
                          {"get": True, "extra": {"retention": True}})
            assert result["retention"] == {
                "datetime": ANY,
                "source": "property",
            }
            assert result["retention"]["datetime"].astimezone(tz) == datetime(2031, 4, 10, 6, 30, tzinfo=tz)
