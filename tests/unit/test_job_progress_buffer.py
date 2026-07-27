import asyncio
import concurrent.futures
import sys
import threading
import time

import pytest

from middlewared.job import JobProgressBuffer


class FakeJob:
    """Minimal stand-in for `middlewared.job.Job` as used by `JobProgressBuffer`."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.progress_calls: list[tuple] = []

    def set_progress(self, percent=None, description=None, extra=None) -> None:
        self.progress_calls.append((percent, description, extra))


@pytest.fixture
def loop_in_thread():
    """Factory for an event loop running in a dedicated thread, like `middlewared`'s.

    Returns `make_loop(debug=False)` -> `(loop, loop_errors)`, where `loop_errors`
    collects anything that escapes `run_forever()` (i.e. anything that would kill the
    middleware event loop).
    """
    loops = []

    def make_loop(debug: bool = False):
        loop = asyncio.new_event_loop()
        loop.set_debug(debug)
        loop_errors: list[BaseException] = []
        started = threading.Event()

        def run():
            asyncio.set_event_loop(loop)
            loop.call_soon(started.set)
            try:
                loop.run_forever()
            except BaseException as e:
                loop_errors.append(e)

        thread = threading.Thread(target=run, name="test_job_event_loop", daemon=True)
        thread.start()
        assert started.wait(5), "event loop did not start"
        loops.append((loop, thread))
        return loop, loop_errors

    try:
        yield make_loop
    finally:
        for loop, thread in loops:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(5)
            loop.close()


def test_progress_buffer_threadsafe(loop_in_thread):
    """
    The loop runs in debug mode, so asyncio itself flags the non-thread-safe call.
    """
    loop, loop_errors = loop_in_thread(debug=True)
    job = FakeJob(loop)
    buffer = JobProgressBuffer(job, interval=0.05)
    worker_errors: list[BaseException] = []

    def worker():
        try:
            # First update goes out immediately, second one is buffered and has to be
            # scheduled on the loop for later delivery.
            buffer.set_progress(0, "first")
            buffer.set_progress(50, "second")
        except BaseException as e:
            worker_errors.append(e)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(5)

    assert not worker_errors, f"set_progress() from a worker thread raised {worker_errors[0]!r}"

    # The buffered update must still be delivered by the loop.
    deadline = time.monotonic() + 5
    while len(job.progress_calls) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert job.progress_calls == [(0, "first", None), (50, "second", None)]
    assert not loop_errors, f"event loop died with {loop_errors[0]!r}"


def test_progress_buffer_threadsafe_nondeterministic(loop_in_thread):
    """
    The loop deliberately runs without debug mode here, so the unsynchronized heap
    access is reached instead of being caught by asyncio's own thread check. The
    thread switch interval is lowered so the interleaving is hit quickly rather than
    once every few nightly backups.
    """
    loop, loop_errors = loop_in_thread(debug=False)
    job = FakeJob(loop)
    # Long interval => every set_progress() after the first one takes the "buffer it
    # and arm a timer" path, and cancel() disarms it again, as restic progress
    # reporting does over the lifetime of a backup.
    buffer = JobProgressBuffer(job, interval=3600)
    stop = threading.Event()
    worker_errors: list[BaseException] = []
    # A corrupted heap can blow up in whichever thread touches it first, so watch the
    # loop-side timer bookkeeping as well and don't let it be swallowed by the task.
    churn_errors: list[BaseException] = []

    async def churn():
        """Keep the loop busy rebuilding `_scheduled` from cancelled timers."""
        try:
            while not stop.is_set():
                handles = [loop.call_later(3600, int) for _ in range(2000)]
                for handle in handles:
                    handle.cancel()
                await asyncio.sleep(0)
        except BaseException as e:
            churn_errors.append(e)

    def worker():
        try:
            buffer.set_progress(0, "starting")
            while not stop.is_set():
                buffer.set_progress(50, "working")
                buffer.cancel()
        except BaseException as e:
            worker_errors.append(e)

    switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    thread = threading.Thread(target=worker, name="test_job_progress_worker")
    try:
        asyncio.run_coroutine_threadsafe(churn(), loop)
        thread.start()

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (loop_errors or worker_errors or churn_errors):
            time.sleep(0.05)
    finally:
        stop.set()
        thread.join(5)
        sys.setswitchinterval(switch_interval)

    assert not worker_errors, f"set_progress() from a worker thread raised {worker_errors[0]!r}"
    assert not churn_errors, f"event loop timer bookkeeping raised {churn_errors[0]!r}"
    assert not loop_errors, f"event loop died with {loop_errors[0]!r}"

    # A dead loop still accepts callbacks, it just never runs them.
    future: concurrent.futures.Future = concurrent.futures.Future()
    loop.call_soon_threadsafe(lambda: future.set_result(True))
    try:
        assert future.result(5)
    except concurrent.futures.TimeoutError:
        pytest.fail("event loop is no longer processing callbacks")
