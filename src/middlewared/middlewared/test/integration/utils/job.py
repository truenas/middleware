# -*- coding=utf-8 -*-
import contextlib
import logging
from datetime import datetime
from types import SimpleNamespace

from .call import call

logger = logging.getLogger(__name__)

__all__ = ["assert_creates_job"]

UNITIALIZED_TS = datetime.fromtimestamp(0)


@contextlib.contextmanager
def assert_creates_job(method):
    newest_job_ts = UNITIALIZED_TS
    if jobs := call("core.get_jobs"):
        newest_job_ts = jobs[-1]["time_started"]

    job = SimpleNamespace(id=None)
    yield job

    jobs = call("core.get_jobs", [["method", "=", method]])
    if not jobs or jobs[-1]["time_started"] <= newest_job_ts:
        raise RuntimeError(f"{method} was not started")

    job.id = jobs[-1]["id"]
