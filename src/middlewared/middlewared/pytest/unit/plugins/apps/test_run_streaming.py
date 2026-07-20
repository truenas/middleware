import threading
import time
from types import SimpleNamespace
import typing

import pytest

from middlewared.job import Job, JobCancelledException
from middlewared.plugins.apps.utils import run_streaming


def make_job():
    return typing.cast("Job", SimpleNamespace(aborted_event=threading.Event()))


def test_streams_lines_before_process_exits(tmp_path):
    # The script blocks after its first line until the callback creates the flag file, so the
    # test deadlocks (and times out) unless lines are delivered while the process still runs.
    flag = tmp_path / "flag"
    script = f"echo first >&2; until [ -f {flag} ]; do sleep 0.05; done; echo second >&2"
    lines = []

    def callback(line):
        lines.append(line)
        flag.touch()

    cp = run_streaming(["bash", "-c", script], line_callback=callback, timeout=30)

    assert cp.returncode == 0
    assert lines == ["first\n", "second\n"]
    assert cp.stderr == "first\nsecond\n"


def test_timeout_kills_whole_process_group():
    # The grandchild inherits stderr; unless the whole process group is killed on timeout, it
    # keeps the pipe open and the stderr reader (joined with its own timeout) stalls the return.
    script = "(sleep 30; echo late >&2) & sleep 30"
    start = time.monotonic()

    cp = run_streaming(["bash", "-c", script], line_callback=lambda _: None, timeout=1)

    assert cp.returncode == -1
    assert cp.stderr == "Timed out waiting for response"
    assert time.monotonic() - start < 5


def test_abort_kills_process_and_raises():
    job = make_job()
    threading.Timer(0.3, job.aborted_event.set).start()
    start = time.monotonic()

    with pytest.raises(JobCancelledException):
        run_streaming(["bash", "-c", "sleep 30"], line_callback=lambda _: None, timeout=30, job=job)

    assert time.monotonic() - start < 5


def test_callback_failure_does_not_interrupt_streaming():
    def callback(line):
        raise ValueError(line)

    cp = run_streaming(["bash", "-c", "echo first >&2; echo second >&2"], line_callback=callback, timeout=30)

    assert cp.returncode == 0
    assert cp.stderr == "first\nsecond\n"
