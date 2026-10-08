import contextlib

import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, client, mock, poll, ssh

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

LOCAL_REPLICATION_TASK = {
    "direction": "PUSH",
    "transport": "LOCAL",
    "recursive": False,
    "name_regex": ".+",
    "auto": False,
    "retention_policy": "NONE",
}


def wait_for_daemon():
    poll(
        lambda: call("zettarepl.is_running"),
        timeout=120,
        message="The zettarepl daemon never reattached",
    )


@pytest.fixture(scope="module", autouse=True)
def attached_daemon():
    # Every test here assumes middleware already has a daemon. After a middleware restart the daemon needs a
    # few seconds to notice and reconnect.
    wait_for_daemon()


@contextlib.contextmanager
def stopped_daemon():
    ssh("systemctl stop zettarepl.service")
    try:
        poll(
            lambda: call("zettarepl.is_running") is False,
            timeout=60,
            message="The zettarepl daemon never detached",
        )
        yield
    finally:
        ssh("systemctl start zettarepl.service")
        wait_for_daemon()


def status(running=(), pending=()):
    return {"running": list(running), "pending": list(pending)}


def test_get_definition_carries_a_generation():
    """Every definition rebuild bumps the generation the daemon uses to tell pushes apart."""
    first = call("zettarepl.get_definition")
    assert first["generation"] > 0
    assert "periodic-snapshot-tasks" in first["definition"]
    assert "replication-tasks" in first["definition"]

    call("zettarepl.update_tasks")

    second = call("zettarepl.get_definition")
    assert second["generation"] > first["generation"]


def test_report_survives_malformed_and_unknown_items():
    """One bad item in a batch must not stop middleware from processing the rest of it."""
    with dataset("malformed_src") as src, dataset("malformed_dst") as dst:
        call("pool.snapshot.create", {"dataset": src, "name": "malformed-1"})

        with replication_task(
            {
                **LOCAL_REPLICATION_TASK,
                "name": "test_malformed_report",
                "source_datasets": [src],
                "target_dataset": f"{dst}/target",
            }
        ) as task:
            task_id = f"task_{task['id']}"

            with client() as c:
                c.call(
                    "zettarepl.notify",
                    [
                        # Unknown message type
                        {
                            "type": "SomethingMiddlewareHasNeverHeardOf",
                            "task_id": task_id,
                        },
                        # Known message type, missing a required field
                        {"type": "ReplicationTaskLog", "task_id": task_id},
                        # Valid, and must still be applied
                        {
                            "type": "ReplicationTaskError",
                            "task_id": task_id,
                            "error": "Reported after the bad items",
                        },
                    ],
                )

                state = call("replication.get_instance", task["id"])["state"]
                assert state["state"] == "ERROR"
                assert "Reported after the bad items" in state["error"]


def test_definition_errors_are_reported_per_task():
    """`notify_definition_read` turns the daemon's parse errors into per-task error states."""
    with dataset("deferr_src") as src, dataset("deferr_dst") as dst:
        call("pool.snapshot.create", {"dataset": src, "name": "deferr-1"})

        with replication_task(
            {
                **LOCAL_REPLICATION_TASK,
                "name": "test_definition_errors",
                "source_datasets": [src],
                "target_dataset": f"{dst}/target",
            }
        ) as rt:
            with snapshot_task({**TASK_DATA, "dataset": src}) as st:
                with client() as c:
                    c.call(
                        "zettarepl.notify_definition_read",
                        {
                            "errors": [
                                {
                                    "type": "replication_task",
                                    "task_id": f"task_{rt['id']}",
                                    "error": "Simulated replication task parse failure",
                                },
                                {
                                    "type": "periodic_snapshot_task",
                                    "task_id": f"task_{st['id']}",
                                    "error": "Simulated periodic snapshot task parse failure",
                                },
                                # A definition-wide error has no task to attach to and is dropped here.
                                {
                                    "type": "definition",
                                    "task_id": None,
                                    "error": "Unknown timezone",
                                },
                            ],
                        },
                    )

                    rt_state = call("replication.get_instance", rt["id"])["state"]
                    assert rt_state["state"] == "ERROR"
                    assert "Simulated replication task parse failure" in rt_state["error"]

                    st_state = call("pool.snapshottask.get_instance", st["id"])["state"]
                    assert st_state["state"] == "ERROR"
                    assert "Simulated periodic snapshot task parse failure" in st_state["error"]


def test_notify_status_keeps_tasks_the_daemon_still_runs():
    """A task the daemon still reports as running survives the reconnect reconciliation."""
    with dataset("alive_src") as src, dataset("alive_dst") as dst:
        call("pool.snapshot.create", {"dataset": src, "name": "alive-1"})

        with replication_task(
            {
                **LOCAL_REPLICATION_TASK,
                "name": "test_notify_status_alive",
                "source_datasets": [src],
                "target_dataset": f"{dst}/target",
            }
        ) as task:
            task_id = f"task_{task['id']}"

            with client() as c:
                c.call("zettarepl.notify", [{"type": "ReplicationTaskStart", "task_id": task_id}])
                assert call("replication.get_instance", task["id"])["state"]["state"] == "RUNNING"

                # The daemon still has it, so reconciliation must leave it alone.
                c.call("zettarepl.notify_status", status(running=[task_id]))
                assert call("replication.get_instance", task["id"])["state"]["state"] == "RUNNING"

                # A pending task is alive too.
                c.call("zettarepl.notify_status", status(pending=[task_id]))
                assert call("replication.get_instance", task["id"])["state"]["state"] == "RUNNING"

                # The daemon no longer has it, so it has to be failed.
                c.call("zettarepl.notify_status", status())
                state = call("replication.get_instance", task["id"])["state"]
                assert state["state"] == "ERROR"
                assert "zettarepl service restarted" in state["error"]


def test_running_tasks_require_the_daemon():
    """With the daemon stopped, running a task fails instead of hanging forever."""
    with dataset("nodaemon_src") as src:
        with snapshot_task({**TASK_DATA, "dataset": src}) as st:
            with replication_task(
                {
                    **LOCAL_REPLICATION_TASK,
                    "name": "test_no_daemon",
                    "source_datasets": [src],
                    "target_dataset": "data/dst",
                }
            ) as rt:
                with stopped_daemon():
                    # Both of these are jobs, so the failure arrives as a job error, not a call error.
                    with pytest.raises(ClientException, match="The zettarepl service is not running"):
                        call("pool.snapshottask.run", st["id"], job=True)

                    with pytest.raises(ClientException, match="The zettarepl service is not running"):
                        call("replication.run", rt["id"], job=True)


MOCK_VMWARE_BEGIN = """\
    def mock(self, task_id):
        return {"dataset": "mock", "qs": [{"id": 1}]}
"""
MOCK_VMWARE_PROCEED = """\
    def mock(self, job, context):
        return {"vmsynced": True, "snapname": "mock", "vmsnapobjs": []}
"""
MOCK_VMWARE_END = """\
    def mock(self, job, context):
        return None
"""
MOCK_VMWARE_END_FAILS = """\
    def mock(self, job, context):
        raise Exception("Simulated VMWare finalization failure")
"""
MOCK_VM_BEGIN = """\
    async def mock(self, task_id):
        return {7: [{"id": 7}]}
"""
MOCK_VM_NOOP = """\
    def mock(self, vm_ids):
        return None
"""
MOCK_VM_SUSPEND_FAILS = """\
    def mock(self, vm_ids):
        raise Exception("Simulated suspend failure")
"""


def vmsynced(dataset_name):
    snapshots = call("pool.snapshot.query", [["dataset", "=", dataset_name]])
    assert len(snapshots) == 1
    return ssh(f"zfs get -H -o value freenas:vmsynced {snapshots[0]['name']}").strip()


def test_vmware_snapshot_coordination():
    """The daemon's start hook drives the VMWare and VM suspend cycle and marks the snapshot vmsynced."""
    with dataset("vmsync") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with (
                mock("vmware.periodic_snapshot_task_begin", MOCK_VMWARE_BEGIN),
                mock("vmware.periodic_snapshot_task_proceed", MOCK_VMWARE_PROCEED),
                mock("vmware.periodic_snapshot_task_end", MOCK_VMWARE_END),
                mock("vm.periodic_snapshot_task_begin", MOCK_VM_BEGIN),
                mock("vm.suspend_vms", MOCK_VM_NOOP),
                mock("vm.resume_suspended_vms", MOCK_VM_NOOP),
            ):
                call("pool.snapshottask.run", task["id"], job=True)

                assert vmsynced(ds) == "Y"
                assert call("pool.snapshottask.get_instance", task["id"])["state"]["state"] == "FINISHED"


def test_vmware_failures_do_not_stop_the_snapshot():
    """A failed VM suspend and a failed VMWare finalization are both logged and swallowed."""
    with dataset("vmsync_fail") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with (
                mock("vmware.periodic_snapshot_task_begin", MOCK_VMWARE_BEGIN),
                mock("vmware.periodic_snapshot_task_proceed", MOCK_VMWARE_PROCEED),
                mock("vmware.periodic_snapshot_task_end", MOCK_VMWARE_END_FAILS),
                mock("vm.periodic_snapshot_task_begin", MOCK_VM_BEGIN),
                mock("vm.suspend_vms", MOCK_VM_SUSPEND_FAILS),
                mock("vm.resume_suspended_vms", MOCK_VM_NOOP),
            ):
                call("pool.snapshottask.run", task["id"], job=True)

                # The suspend failed, but the VMWare snapshots succeeded, so the marking still happens.
                assert vmsynced(ds) == "Y"
                assert call("pool.snapshottask.get_instance", task["id"])["state"]["state"] == "FINISHED"


def test_no_vmware_objects_leaves_the_snapshot_unmarked():
    """Without VMWare objects for the dataset, no properties are added to the snapshot."""
    with dataset("vmsync_none") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            call("pool.snapshottask.run", task["id"], job=True)

            assert vmsynced(ds) == "-"
