import errno

import pytest
from functions import http_get

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, mock, url


@pytest.fixture(scope="module")
def c():
    with unprivileged_user_client(roles=["MOCK"]) as c:
        yield c


@pytest.fixture(scope="module")
def c_replication_read():
    with unprivileged_user_client(roles=["REPLICATION_TASK_READ"]) as c:
        yield c


def test_job_download_logs(c):
    with mock("test.test1", """    
        from middlewared.service import job

        @job(logs=True)
        def mock(self, job, *args):
            job.logs_fd.write(b'Job logs')
    """):
        jid = c.call("test.test1")

        c.call("core.job_wait", jid, job=True)

        path = c.call("core.job_download_logs", jid, "logs.txt")

        r = http_get(f"{url()}{path}")
        r.raise_for_status()

        assert r.headers["Content-Disposition"] == "attachment; filename=\"logs.txt\""
        assert r.headers["Content-Type"] == "application/octet-stream"
        assert r.text == "Job logs"


def test_job_download_logs_unprivileged_downloads_internal_logs(c):
    with mock("test.test1", """
        def mock(self, *args):
            job = self.middleware.call_sync("test.test2")
            job.wait_sync(raise_error=True)
            return job.id
    """):
        with mock("test.test2", """
            from middlewared.service import job

            @job(logs=True)
            def mock(self, job, *args):
                job.logs_fd.write(b'Job logs')
        """):
            jid = call("test.test1")

            with pytest.raises(CallError) as ve:
                c.call("core.job_download_logs", jid, "logs.txt")

            assert ve.value.errno == errno.EPERM


def test_job_download_logs_unprivileged_downloads_internal_logs_with_read_role(c_replication_read):
    with mock("test.test1", """
        from middlewared.service import job

        @job(logs=True, read_roles=["REPLICATION_TASK_READ"])
        def mock(self, job, *args):
            job.logs_fd.write(b'Job logs')
    """):
        c = c_replication_read

        jid = call("test.test1")

        c.call("core.job_wait", jid, job=True)

        path = c.call("core.job_download_logs", jid, "logs.txt")

        r = http_get(f"{url()}{path}")
        r.raise_for_status()

        assert r.headers["Content-Disposition"] == "attachment; filename=\"logs.txt\""
        assert r.headers["Content-Type"] == "application/octet-stream"
        assert r.text == "Job logs"
