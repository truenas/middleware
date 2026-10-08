import json

import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, mock, poll

from truenas_api_client import ClientException


MOCK_GET_STATE_GLOBAL_ERROR = """\
    async def mock(self):
        return {"error": "Simulated global zettarepl failure"}
"""
MOCK_GET_STATE_TASK_STATE = """\
    async def mock(self):
        class Tasks(dict):
            def get(self, key, default=None):
                return %r
        return {"tasks": Tasks()}
"""

SNAPSHOT_TASK = {
    "recursive": False,
    "lifetime_value": 1,
    "lifetime_unit": "DAY",
    "naming_schema": "auto-%Y-%m-%d_%H-%M",
    "schedule": {"minute": "0", "hour": "0", "dom": "1", "month": "1", "dow": "1"},
    "enabled": True,
}


def persist_task_state(task_id, state):
    """Write a task state into the database the way `flush_state` does on the other HA node."""
    call("datastore.update", "storage.task", task_id, {"task_state": json.dumps(state)})


def test_run_onetime_global_error_state():
    with dataset("onetime_src") as src, dataset("onetime_dst") as dst:
        with mock("zettarepl.get_state", MOCK_GET_STATE_GLOBAL_ERROR):
            with pytest.raises(ClientException, match="Simulated global zettarepl failure"):
                call(
                    "replication.run_onetime",
                    {
                        "direction": "PUSH",
                        "transport": "LOCAL",
                        "source_datasets": [src],
                        "target_dataset": dst,
                        "recursive": False,
                        "name_regex": ".+",
                        "retention_policy": "NONE",
                    },
                    job=True,
                )


@pytest.mark.parametrize(
    "task_state,match",
    [
        ({"state": "ERROR", "error": "Simulated task error"}, "Simulated task error"),
        ({"state": "HOLD", "reason": "Simulated task hold"}, "Simulated task hold"),
        ({"state": "RUNNING"}, None),
    ],
)
def test_run_onetime_task_state_error(task_state, match):
    with dataset("onetime_src") as src, dataset("onetime_dst") as dst:
        with mock("zettarepl.get_state", MOCK_GET_STATE_TASK_STATE % task_state):
            with pytest.raises(Exception) as e:
                call(
                    "replication.run_onetime",
                    {
                        "direction": "PUSH",
                        "transport": "LOCAL",
                        "source_datasets": [src],
                        "target_dataset": dst,
                        "recursive": False,
                        "name_regex": ".+",
                        "retention_policy": "NONE",
                    },
                    job=True,
                )

            if match:
                assert match in str(e.value)


def test_zettarepl_load_state():
    """`zettarepl.load_state` restores persisted task states from the database."""
    with dataset("loadstate_src") as src, dataset("loadstate_dst") as dst:
        with snapshot_task(
            {
                "dataset": src,
                "recursive": False,
                "lifetime_value": 1,
                "lifetime_unit": "DAY",
                "naming_schema": "auto-%Y-%m-%d_%H-%M",
                "schedule": {"minute": "0", "hour": "0", "dom": "1", "month": "1", "dow": "1"},
                "enabled": True,
            }
        ) as st:
            call("pool.snapshottask.run", st["id"], job=True)

            with replication_task(
                {
                    "name": "test_zettarepl_load_state",
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "also_include_naming_schema": ["auto-%Y-%m-%d_%H-%M"],
                    "auto": False,
                    "retention_policy": "NONE",
                }
            ) as rt:
                call("replication.run", rt["id"], job=True)

                with (
                    snapshot_task(
                        {
                            "dataset": src,
                            "recursive": False,
                            "lifetime_value": 1,
                            "lifetime_unit": "DAY",
                            "naming_schema": "never-%Y-%m-%d_%H-%M",
                            "schedule": {"minute": "0", "hour": "0", "dom": "1", "month": "1", "dow": "1"},
                            "enabled": True,
                        }
                    ) as never_run_st,
                    replication_task(
                        {
                            "name": "test_zettarepl_load_state never run",
                            "direction": "PUSH",
                            "transport": "LOCAL",
                            "source_datasets": [src],
                            "target_dataset": "data/dst",
                            "recursive": False,
                            "name_regex": ".+",
                            "auto": False,
                            "retention_policy": "NONE",
                        }
                    ) as never_run_rt,
                ):
                    call("zettarepl.load_state")

                    # A task that has never run has an empty persisted state, and loading it must not register a
                    # state entry for the task
                    assert call("pool.snapshottask.get_instance", never_run_st["id"])["state"]["state"] == "PENDING"
                    assert call("replication.get_instance", never_run_rt["id"])["state"]["state"] == "PENDING"

                assert call("pool.snapshottask.get_instance", st["id"])["state"]["state"] == "FINISHED"
                assert call("replication.get_instance", rt["id"])["state"]["state"] == "FINISHED"


def test_load_state_restores_lost_in_memory_state():
    """`zettarepl.load_state` restores the state of a task that zettarepl no longer holds in memory.

    This is what a promoted HA node does. It never loaded the state the old active node replicated into the
    database after this node booted.
    """
    with dataset("restore_src") as src, dataset("restore_dst") as dst:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            call("pool.snapshottask.run", st["id"], job=True)

            with replication_task(
                {
                    "name": "test_load_state_restores_lost_in_memory_state",
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "also_include_naming_schema": ["auto-%Y-%m-%d_%H-%M"],
                    "auto": False,
                    "retention_policy": "NONE",
                }
            ) as rt:
                call("replication.run", rt["id"], job=True)

                call("zettarepl.remove_task", f"periodic_snapshot_task_{st['id']}")
                call("zettarepl.remove_task", f"replication_task_{rt['id']}")
                assert call("pool.snapshottask.get_instance", st["id"])["state"]["state"] == "PENDING"
                assert call("replication.get_instance", rt["id"])["state"]["state"] == "PENDING"

                call("zettarepl.load_state")

                snapshot_task_state = call("pool.snapshottask.get_instance", st["id"])["state"]
                assert snapshot_task_state["state"] == "FINISHED"
                assert snapshot_task_state["last_snapshot"].startswith(f"{src}@auto-")

                replication_task_state = call("replication.get_instance", rt["id"])["state"]
                assert replication_task_state["state"] == "FINISHED"
                assert replication_task_state["last_snapshot"].startswith(f"{src}@auto-")


def test_disabled_task_keeps_its_state():
    """Disabling a periodic snapshot task keeps the state of its last run."""
    with dataset("disabled_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            call("pool.snapshottask.run", st["id"], job=True)
            call("pool.snapshottask.update", st["id"], {"enabled": False})

            state = call("pool.snapshottask.get_instance", st["id"])["state"]
            assert state["state"] == "FINISHED"
            assert state["last_snapshot"].startswith(f"{src}@auto-")


def test_load_state_restores_error_state_and_alert():
    """A task that failed on the other HA node reports `ERROR` and raises `SnapshotFailed` after the state loads."""
    with dataset("error_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            persist_task_state(st["id"], {
                "state": {
                    "state": "ERROR",
                    "datetime": {"$date": 1700000000000},
                    "error": "Simulated replicated failure",
                },
            })
            call("zettarepl.load_state")

            state = call("pool.snapshottask.get_instance", st["id"])["state"]
            assert state["state"] == "ERROR"
            assert state["error"] == "Simulated replicated failure"

            alerts = call("alert.run_source", "Replication")
            assert [
                alert for alert in alerts
                if alert["klass"] == "SnapshotFailed" and alert["args"]["id"] == st["id"]
            ], alerts


def test_persisted_last_snapshot_without_state_reports_pending():
    """A persisted state that holds only `last_snapshot` reports `PENDING` instead of omitting the state."""
    with dataset("pending_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            last_snapshot = f"{src}@auto-2026-01-01_00-00"
            persist_task_state(st["id"], {"last_snapshot": last_snapshot})
            call("zettarepl.load_state")

            state = call("pool.snapshottask.get_instance", st["id"])["state"]
            assert state["state"] == "PENDING"
            assert state["last_snapshot"] == last_snapshot

            alerts = call("alert.run_source", "Replication")
            assert not [alert for alert in alerts if alert["klass"] == "AlertSourceRunFailed"], alerts


def test_load_state_forgets_tasks_without_a_row():
    """`zettarepl.load_state` drops the state of tasks that no longer exist in the database.

    The other HA node deletes rows through SQL replication, which does not reach this node's in-memory state.
    A task id reused by a new task would otherwise inherit the deleted task's state.
    """
    with dataset("forget_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            call("pool.snapshottask.run", st["id"], job=True)

            task_id = f"periodic_snapshot_task_{st['id']}"
            assert call("zettarepl.get_state")["tasks"][task_id]["state"] == "FINISHED"

            call("datastore.delete", "storage.task", st["id"])
            call("zettarepl.load_state")

            assert task_id not in call("zettarepl.get_state")["tasks"]


def test_deleting_task_forgets_its_state():
    """Deleting a periodic snapshot task drops its state, so a reused task id does not inherit it."""
    with dataset("reuse_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            call("pool.snapshottask.run", st["id"], job=True)

        assert f"periodic_snapshot_task_{st['id']}" not in call("zettarepl.get_state")["tasks"]


def test_zettarepl_terminate_and_restart():
    """`zettarepl.terminate` flushes the task states and stops the zettarepl service."""
    call("zettarepl.terminate")
    assert call("zettarepl.is_running") is False

    call("zettarepl.start")
    poll(
        lambda: call("zettarepl.is_running"),
        timeout=60,
        message="The zettarepl service never started",
    )
