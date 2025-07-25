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


def busy_wait_on_job(jobid: int, max_timeout: int = 600, delay: int = 5, /, call_fn=call):
    start_time = time.monotonic()
    while time.monotonic() - start_time < max_timeout:
        jobs = call_fn('core.get_jobs', [['id', '=', jobid]])
        job_state = jobs[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            time.sleep(delay)
        elif job_state == 'SUCCESS':
            return True
        elif job_state == 'FAILED':
            raise ValueError(f'Job {jobid} failed: {jobs[0]}')
    # Fell out of loop, so timed out
    raise ValueError(f'Job {jobid} timed out ({max_timeout}): {jobs[0]}')
