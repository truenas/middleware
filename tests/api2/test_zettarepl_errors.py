import time

import pytest

from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.utils import call, mock, poll, ssh


@pytest.fixture(scope="module")
def ssh_credentials():
    with localhost_ssh_credentials(username="root") as c:
        yield c


RAISE_SET_DEFINITION_ERRORS = """\
    def mock(self, definition_errors):
        raise Exception("Simulated observer queue reader failure")
"""


def test_observer_queue_reader_survives_exceptions():
    """An exception while processing an observer message does not kill the observer queue reader."""
    with dataset("observer_src") as src:
        with replication_task(
            {
                "name": "test_observer_queue_reader",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": "data/dst",
                "recursive": False,
                "name_regex": ".+",
                "auto": False,
                "retention_policy": "NONE",
            }
        ):
            with mock("zettarepl.set_definition_errors", RAISE_SET_DEFINITION_ERRORS):
                # The zettarepl process reports (empty) definition errors for the new set of tasks,
                # and processing that message raises.
                call("zettarepl.update_tasks")

                # The observer queue reader is still alive: the observer queue is FIFO, so this
                # replication completing proves that the poisoned definition errors message queued
                # before its events was already processed.
                with dataset("observer_dst") as dst:
                    call("pool.snapshot.create", {"dataset": src, "name": "observer-1"})
                    call(
                        "replication.run_onetime",
                        {
                            "direction": "PUSH",
                            "transport": "LOCAL",
                            "source_datasets": [src],
                            "target_dataset": f"{dst}/target",
                            "recursive": False,
                            "name_regex": ".+",
                            "retention_policy": "NONE",
                        },
                        job=True,
                    )


def test_zettarepl_process_abnormal_termination(ssh_credentials):
    """Killing the zettarepl process fails running tasks and the process is restarted."""
    with dataset("kill_src") as src, dataset("kill_dst") as dst:
        ssh(f"dd if=/dev/urandom of=/mnt/{src}/blob bs=1M count=6")
        call("pool.snapshot.create", {"dataset": src, "name": "kill-1"})

        with replication_task(
            {
                "name": "test_zettarepl_kill",
                "direction": "PUSH",
                "transport": "SSH",
                "ssh_credentials": ssh_credentials["credentials"]["id"],
                "source_datasets": [src],
                "target_dataset": dst,
                "recursive": False,
                "name_regex": ".+",
                "auto": False,
                "retention_policy": "NONE",
                "speed_limit": 100000,
                "compression": "LZ4",
            }
        ) as task:
            job_id = call("replication.run", task["id"])

            poll(
                lambda: call("replication.get_instance", task["id"]),
                condition=lambda task: (task["state"] or {}).get("state") == "RUNNING",
                timeout=60,
                message="The replication task never started running",
            )

            # `-x` matches the process name only; `-f` would also match (and kill) the SSH login
            # shell that runs this very command.
            ssh("pkill -9 -x mw-zettarepl")

            def finished_job():
                job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
                if job["state"] in ("SUCCESS", "FAILED", "ABORTED"):
                    return job
                return None

            job = poll(
                finished_job,
                timeout=60,
                message="The replication job never finished after the zettarepl process was killed",
            )
            assert job["state"] == "FAILED"
            assert "Abnormal zettarepl process termination" in job["error"]

            state = call("replication.get_instance", task["id"])["state"]
            assert state["state"] == "ERROR"
            assert "Abnormal zettarepl process termination" in state["error"]

            # The zettarepl process is automatically restarted.
            poll(
                lambda: call("zettarepl.is_running"),
                timeout=60,
                message="The zettarepl process was never restarted",
            )

            # The killed zettarepl process leaves its send/recv pipeline orphaned. Kill it, or it
            # would finish the transfer later and re-create the target dataset after this test
            # deletes it. (The `[e]` keeps the pattern from matching its own SSH login shell.)
            ssh("pkill -9 -f 'zfs r[e]cv.*kill_dst'", check=False)
            time.sleep(2)
