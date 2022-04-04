import contextlib
import os
import time

import pytest

from middlewared.test.integration.utils import call, mock


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_jobs_execute_in_parallel():
    with mock("test.test1", """    
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            import time
            time.sleep(5)
    """):
        start = time.monotonic()

        j1 = call("test.test1")
        j2 = call("test.test1")
        j3 = call("test.test1")

        call("core.job_wait", j1, job=True)
        call("core.job_wait", j2, job=True)
        call("core.job_wait", j3, job=True)

        assert time.monotonic() - start < 6


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_jobs_execute_sequentially_when_there_is_a_lock():
    with mock("test.test1", """    
        from middlewared.service import job

        @job(lock="test")
        def mock(self, job, *args):
            import time
            time.sleep(5)
    """):
        start = time.monotonic()

        j1 = call("test.test1")
        j2 = call("test.test1")
        j3 = call("test.test1")

        call("core.job_wait", j1, job=True)
        call("core.job_wait", j2, job=True)
        call("core.job_wait", j3, job=True)

        assert time.monotonic() - start >= 15


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_lock_with_argument():
    with mock("test.test1", """    
        from middlewared.service import job

        @job(lock=lambda args: f"test.{args[0]}")
        def mock(self, job, s):
            import time
            time.sleep(5)
    """):
        start = time.monotonic()

        j1 = call("test.test1", "a")
        j2 = call("test.test1", "b")
        j3 = call("test.test1", "a")

        call("core.job_wait", j1, job=True)
        call("core.job_wait", j2, job=True)
        call("core.job_wait", j3, job=True)

        assert 10 <= time.monotonic() - start < 15


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_lock_queue_size():
    try:
        with mock("test.test1", """
            from middlewared.service import job
            
            @job(lock="test", lock_queue_size=1)
            def mock(self, job, *args):
                with open("/tmp/test", "a") as f:
                    f.write("a\\n")
            
                import time
                time.sleep(5)
        """):
            j1 = call("test.test1")
            j2 = call("test.test1")
            j3 = call("test.test1")
            j4 = call("test.test1")

            call("core.job_wait", j1, job=True)
            call("core.job_wait", j2, job=True)
            call("core.job_wait", j3, job=True)
            call("core.job_wait", j4, job=True)

            with open("/tmp/test") as f:
                assert f.read() == "a\na\n"

            assert j3 == j2
            assert j4 == j2
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink("/tmp/test")


def test_call_sync_a_job_with_lock():
    with mock("test.test1", """
        from middlewared.service import job

        def mock(self):
            return self.middleware.call_sync("test.test2").wait_sync()
    """):
        with mock("test.test2", """
            from middlewared.service import job

            @job(lock="test")
            def mock(self, job, *args):
                return 42
        """):
            assert call("test.test1") == 42
