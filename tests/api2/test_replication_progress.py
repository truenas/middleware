import pytest

from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.utils import call, poll, ssh


@pytest.fixture(scope="module")
def ssh_credentials():
    with localhost_ssh_credentials(username="root") as c:
        yield c


def _poll_replication(id_, predicate, timeout, message):
    return poll(
        lambda: call("replication.get_instance", id_),
        condition=predicate,
        timeout=timeout,
        message=message,
    )


def test_replication_progress_and_concurrent_task_waiting(ssh_credentials):
    """A slow replication reports snapshot/data progress; a concurrent task reports why it waits."""
    original = call("replication.config.config")["max_parallel_replication_tasks"]
    call("replication.config.update", {"max_parallel_replication_tasks": 1})
    try:
        with (
            dataset("progress_src") as src,
            dataset("progress_dst") as dst,
            dataset("waiting_src") as src2,
            dataset("waiting_dst") as dst2,
        ):
            # An incompressible blob that takes about a minute at the configured speed limit, so
            # both the 10 second snapshot progress poll and the 30 second data progress poll fire.
            ssh(f"dd if=/dev/urandom of=/mnt/{src}/blob bs=1M count=6")
            call("pool.snapshot.create", {"dataset": src, "name": "progress-1"})
            call("pool.snapshot.create", {"dataset": src2, "name": "progress-1"})

            with replication_task(
                {
                    "name": "test_progress_slow",
                    "direction": "PUSH",
                    "transport": "SSH",
                    "ssh_credentials": ssh_credentials["credentials"]["id"],
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "name_regex": ".+",
                    "auto": False,
                    "retention_policy": "NONE",
                    # No compression: the snapshot progress observer watches the `zfs send` process
                    # title, and with a compression program in the pipe `zfs send` finishes almost
                    # immediately (the compressor buffers the whole stream) while `mbuffer` is still
                    # slowly draining it.
                    "speed_limit": 100000,
                }
            ) as slow_task:
                with replication_task(
                    {
                        "name": "test_progress_waiting",
                        "direction": "PUSH",
                        "transport": "LOCAL",
                        "source_datasets": [src2],
                        "target_dataset": dst2,
                        "recursive": False,
                        "name_regex": ".+",
                        "auto": False,
                        "retention_policy": "NONE",
                    }
                ) as waiting_task:
                    slow_job = call("replication.run", slow_task["id"])

                    _poll_replication(
                        slow_task["id"],
                        lambda task: (task["state"] or {}).get("state") == "RUNNING",
                        60,
                        "The slow replication task never started running",
                    )

                    # Only one replication task may run at a time now, so this one has to wait.
                    waiting_job = call("replication.run", waiting_task["id"])
                    waiting = _poll_replication(
                        waiting_task["id"],
                        lambda task: (task["state"] or {}).get("state") == "WAITING",
                        60,
                        "The concurrent replication task never started waiting",
                    )
                    assert "Waiting" in waiting["state"]["reason"]

                    # Snapshot progress: "Sending 1 of 1: dataset@snapshot (1.2 MiB / 6.0 MiB)",
                    # then data progress appends " [total ... of ...]".
                    def slow_job_progress_description():
                        job = call("core.get_jobs", [["id", "=", slow_job]], {"get": True})
                        description = job["progress"]["description"] or ""
                        if "(" in description and "[total" in description:
                            return description
                        return None

                    poll(
                        slow_job_progress_description,
                        timeout=120,
                        message="The slow replication job never reported snapshot and data progress",
                    )

                    call("core.job_wait", slow_job, job=True)
                    call("core.job_wait", waiting_job, job=True)

                    assert call("replication.get_instance", slow_task["id"])["state"]["state"] == "FINISHED"
                    assert call("replication.get_instance", waiting_task["id"])["state"]["state"] == "FINISHED"
    finally:
        call("replication.config.update", {"max_parallel_replication_tasks": original})
