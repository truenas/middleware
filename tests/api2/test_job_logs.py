import requests

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import mock, url


def test_job_download_logs():
    with mock("test.test1", """    
        from middlewared.service import job

        @job(logs=True)
        def mock(self, job, *args):
            job.logs_fd.write(b'Job logs')
    """):
        with unprivileged_user_client(allowlist=[{"method": "CALL", "resource": "test.test1"}]) as c:
            jid = c.call("test.test1")

            c.call("core.job_wait", jid, job=True)

            path = c.call("core.job_download_logs", jid, 'logs.txt')

            r = requests.get(f"{url()}{path}")
            r.raise_for_status()

            assert r.headers["Content-Disposition"] == "attachment; filename=\"logs.txt\""
            assert r.headers["Content-Type"] == "application/octet-stream"
            assert r.text == "Job logs"
