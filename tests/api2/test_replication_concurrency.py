import contextlib

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, poll

# Number of `replication.run_onetime` jobs submitted at once.
TASK_COUNT = 10

# How long all of those jobs are given to reach a final state.
TIMEOUT = 30

FINAL_STATES = ("SUCCESS", "FAILED", "ABORTED")

# Submitting the jobs one by one over the websocket would spread them out over a round trip each, which is too slow to
# race the zettarepl scheduler. Submitting them from within a single middleware call gets all of the `run_task`
# commands into the zettarepl command queue at once.
START_JOBS = """\
import asyncio


async def mock(self, payloads):
    jobs = await asyncio.gather(*[
        self.middleware.call("replication.run_onetime", payload)
        for payload in payloads
    ])

    return [job.id for job in jobs]
"""


def test_concurrent_run_onetime_jobs():
    """Every `replication.run_onetime` job submitted at once reaches a final state."""
    with dataset("replication-race") as parent:
        with contextlib.ExitStack() as stack:
            payloads = []
            for i in range(TASK_COUNT):
                source = stack.enter_context(dataset(f"replication-race/source-{i}"))
                call("pool.snapshot.create", {"dataset": source, "name": f"race-{i}"})
                payloads.append(
                    {
                        "direction": "PUSH",
                        "transport": "LOCAL",
                        "source_datasets": [source],
                        "target_dataset": f"{parent}/target-{i}",
                        "recursive": False,
                        "properties": False,
                        "name_regex": f"^race-{i}$",
                        "readonly": "IGNORE",
                        "retention_policy": "NONE",
                        "only_from_scratch": True,
                    }
                )

            with mock("test.test1", START_JOBS):
                job_ids = call("test.test1", payloads)

            assert len(job_ids) == TASK_COUNT, job_ids
            # A burst of calls to the same method can share a job, so the same id may come back more than once.
            job_ids = sorted(set(job_ids))

            def unfinished_jobs():
                return {
                    job["id"]: job["state"]
                    for job in call("core.get_jobs", [["id", "in", job_ids]])
                    if job["state"] not in FINAL_STATES
                }

            poll(
                unfinished_jobs,
                condition=lambda unfinished: not unfinished,
                timeout=TIMEOUT,
                message=f"Not all of the {len(job_ids)} replication jobs completed",
            )

            jobs = call("core.get_jobs", [["id", "in", job_ids]])
            assert all(job["state"] == "SUCCESS" for job in jobs), [
                (job["id"], job["state"], job["error"]) for job in jobs if job["state"] != "SUCCESS"
            ]
