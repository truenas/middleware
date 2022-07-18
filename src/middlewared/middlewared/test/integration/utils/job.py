# -*- coding=utf-8 -*-
import contextlib
import logging
from types import SimpleNamespace

from .call import call

logger = logging.getLogger(__name__)

__all__ = ["assert_creates_job"]


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
