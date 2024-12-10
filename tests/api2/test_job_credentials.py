from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, mock


def test_job_credentials():
    with mock("test.test1", """    
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            return 42
    """):
        with unprivileged_user_client(allowlist=[{"method": "CALL", "resource": "test.test1"}]) as c:
            job_id = c.call("test.test1")

            job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})

            assert job["credentials"] == {"type": "LOGIN_PASSWORD", "data": {"username": c.username}}


def test_job_configservice_credentials():
    # NOTE: using ldap plugin because it's a ConfigService
    # for which do_update is also a job

    # no-op job
    job_id = call('ldap.update', {'enable': False})

    job_data = call('core.get_jobs', [['id', '=', job_id]], {'get': True})
    assert job_data['credentials'] is not None
