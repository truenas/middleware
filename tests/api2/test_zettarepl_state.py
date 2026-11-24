import json
from datetime import datetime, timezone

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, poll, ssh

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


def run_snapshot_task(task_id):
    """Run a periodic snapshot task and wait until it reaches a final state.

    `pool.snapshottask.run` only queues the task for zettarepl, so the state changes later. `RUNNING` is not
    final: zettarepl reports it before it creates the snapshot. Waiting for any final state lets the caller
    assert on `FINISHED` itself.
    """
    call("pool.snapshottask.run", task_id)
    return poll(
        lambda: call("pool.snapshottask.get_instance", task_id)["state"],
        condition=lambda state: state["state"] in ("FINISHED", "ERROR"),
        timeout=60,
        message=f"Periodic snapshot task {task_id} did not run",
    )


def test_load_state_restores_lost_in_memory_state():
    """`zettarepl.load_state` restores the state of a task that zettarepl no longer holds in memory.

    This is what a promoted HA node does. It never loaded the state the old active node replicated into the
    database after this node booted.
    """
    with dataset("restore_src") as src, dataset("restore_dst") as dst:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            run_snapshot_task(st["id"])

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
            run_snapshot_task(st["id"])
            call("pool.snapshottask.update", st["id"], {"enabled": False})

            state = call("pool.snapshottask.get_instance", st["id"])["state"]
            assert state["state"] == "FINISHED"
            assert state["last_snapshot"].startswith(f"{src}@auto-")


def test_load_state_restores_error_state_and_alert():
    """A task that failed on the other HA node reports `ERROR` and raises `SnapshotFailed` after the state loads."""
    with dataset("error_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            persist_task_state(
                st["id"],
                {
                    "state": {
                        "state": "ERROR",
                        "datetime": {"$date": 1700000000000},
                        "error": "Simulated replicated failure",
                    },
                },
            )
            call("zettarepl.load_state")

            state = call("pool.snapshottask.get_instance", st["id"])["state"]
            assert state["state"] == "ERROR"
            assert state["error"] == "Simulated replicated failure"

            alerts = call("alert.run_source", "Replication")
            assert [alert for alert in alerts if alert["klass"] == "SnapshotFailed" and alert["args"]["name"] == src], (
                alerts
            )


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
    A task id reused by a new task would otherwise inherit the deleted task's state. `flush_state` skips the
    state of the missing row instead of failing.
    """
    with dataset("forget_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            run_snapshot_task(st["id"])

            task_id = f"periodic_snapshot_task_{st['id']}"
            assert call("zettarepl.get_state")["tasks"][task_id]["state"] == "FINISHED"

            call("datastore.delete", "storage.task", st["id"])
            call("zettarepl.flush_state")
            call("zettarepl.load_state")

            assert task_id not in call("zettarepl.get_state")["tasks"]


def test_deleting_task_forgets_its_state():
    """Deleting a periodic snapshot task drops its state, so a reused task id does not inherit it."""
    with dataset("reuse_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            run_snapshot_task(st["id"])

        assert f"periodic_snapshot_task_{st['id']}" not in call("zettarepl.get_state")["tasks"]


def test_deleted_task_ignores_late_state():
    """State that zettarepl reports after `pool.snapshottask.delete` does not bring the task back.

    The delete can run while the task is `RUNNING`. Its `FINISHED` report arrives after `zettarepl.remove_task`.
    """
    with dataset("late_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            pass

        task_id = f"periodic_snapshot_task_{st['id']}"
        call("zettarepl.set_last_snapshot", task_id, f"{src}@auto-2026-01-01_00-00")
        call(
            "zettarepl.set_state",
            task_id,
            {"state": "FINISHED", "datetime": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        )

        assert task_id not in call("zettarepl.get_state")["tasks"]


def test_task_on_a_missing_pool_is_held():
    """A periodic snapshot task whose pool is not on the system reports `HOLD` with the reason.

    A config restore brings back tasks for pools that are missing from the system.
    """
    task_id = call(
        "datastore.insert", "storage.task", {"dataset": "nopool/held_src", "exclude": []}, {"prefix": "task_"}
    )
    try:
        call("zettarepl.update_tasks")

        state = call("pool.snapshottask.get_instance", task_id)["state"]
        assert state["state"] == "HOLD"
        assert state["reason"] == "Pool nopool does not exist."
    finally:
        call("datastore.delete", "storage.task", task_id)
        call("zettarepl.update_tasks")


def test_failed_run_reports_error_and_alert():
    """A run that fails reports `ERROR` with the zfs message and raises `SnapshotFailed`.

    The test destroys the dataset outside middleware, so the task stays and `zfs snapshot` fails.
    """
    with dataset("failed_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            ssh(f"zfs destroy -r {src}")

            state = run_snapshot_task(st["id"])
            assert state["state"] == "ERROR"
            assert src in state["error"]

            alerts = call("alert.run_source", "Replication")
            assert [alert for alert in alerts if alert["klass"] == "SnapshotFailed" and alert["args"]["name"] == src], (
                alerts
            )


def test_global_error_replaces_every_task_state():
    """While zettarepl reports a global error, every task reports that error instead of its own state.

    `zettarepl.update_tasks` clears the error once it builds the definition again.
    """
    with dataset("global_error_src") as src:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            run_snapshot_task(st["id"])

            error = {
                "state": "ERROR",
                "datetime": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "error": "Simulated definition failure",
            }
            call("zettarepl.set_error", error)
            try:
                assert call("zettarepl.get_state") == {"error": error}
                assert call("pool.snapshottask.get_instance", st["id"])["state"] == error
            finally:
                call("zettarepl.update_tasks")

            assert call("pool.snapshottask.get_instance", st["id"])["state"]["state"] == "FINISHED"


def test_onetime_replication_task_leaves_no_state():
    """A one-time replication drops its state once it finishes.

    It has no row to keep the state for, and nothing reads it after the job ends.
    """
    with dataset("onetime_src") as src, dataset("onetime_dst") as dst:
        with snapshot_task({**SNAPSHOT_TASK, "dataset": src}) as st:
            run_snapshot_task(st["id"])

            call(
                "replication.run_onetime",
                {
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "also_include_naming_schema": ["auto-%Y-%m-%d_%H-%M"],
                    "retention_policy": "NONE",
                },
                job=True,
            )

            job = call(
                "core.get_jobs", [["method", "=", "replication.run_onetime"]], {"order_by": ["-id"], "get": True}
            )
            assert f"replication_job_{job['id']}" not in call("zettarepl.get_state")["tasks"]
