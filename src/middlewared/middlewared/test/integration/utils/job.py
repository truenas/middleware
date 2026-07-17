# -*- coding=utf-8 -*-
import contextlib
import logging
import time
from types import SimpleNamespace

from .call import call

logger = logging.getLogger(__name__)

__all__ = ["assert_creates_job",
           "busy_wait_on_job"]


@contextlib.contextmanager
def assert_creates_job(method):
    newest_job_id = 0
    if jobs := call("core.get_jobs"):
        newest_job_id = jobs[-1]["id"]

    job = SimpleNamespace(id=None)
    yield job

    jobs = call("core.get_jobs", [["method", "=", method]])
    if not jobs or jobs[-1]["id"] <= newest_job_id:
        raise RuntimeError(f"{method} was not started")

    job.id = jobs[-1]["id"]


def busy_wait_on_job(jobid: int, max_timeout: int = 600, delay: int = 5, /, call_fn=call, stall_timeout=None):
    """
    Poll `jobid` until it succeeds (returning True) or fails (raising ValueError).

    Raises after `max_timeout` seconds overall or, if `stall_timeout` is set, after that many
    seconds without any change in the job's reported progress. Jobs that report continuous
    progress (e.g. app operations streaming docker compose pull events) can use a small
    `stall_timeout` to fail fast on genuine hangs while still tolerating slow-but-alive
    operations that would need a generous `max_timeout`.
    """
    start_time = stall_start = time.monotonic()
    last_progress = None
    while time.monotonic() - start_time < max_timeout:
        jobs = call_fn('core.get_jobs', [['id', '=', jobid]])
        job_state = jobs[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            # Stall detection only applies to running jobs; a job waiting on a lock or queue
            # slot legitimately reports no progress
            if stall_timeout is not None and job_state == 'RUNNING':
                now = time.monotonic()
                if jobs[0]['progress'] != last_progress:
                    last_progress = jobs[0]['progress']
                    stall_start = now
                elif now - stall_start >= stall_timeout:
                    raise ValueError(f'Job {jobid} made no progress for {stall_timeout} seconds: {jobs[0]}')
            time.sleep(delay)
        elif job_state == 'SUCCESS':
            return True
        elif job_state == 'FAILED':
            raise ValueError(f'Job {jobid} failed: {jobs[0]}')
    # Fell out of loop, so timed out
    raise ValueError(f'Job {jobid} timed out ({max_timeout}): {jobs[0]}')
