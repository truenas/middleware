from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, mock
from unittest.mock import ANY


def test_job_credentials():
    with mock("test.test1", """    
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            return 42
    """):
        with unprivileged_user_client(roles=["FULL_ADMIN"]) as c:

            job_id = c.call("test.test1")

            job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})

            expected_creds = {
                "type": "LOGIN_PASSWORD",
                "data": {"username": c.username, "login_at": ANY, "login_id": ANY}
            }

            assert job["credentials"] == expected_creds


def test_job_configservice_credentials():
    # NOTE: using directoryservice plugin because it's a ConfigService
    # for which do_update is also a job

    # no-op job
    job_id = call('directoryservices.update', {'enable': False})

    job_data = call('core.get_jobs', [['id', '=', job_id]], {'get': True})
    assert job_data['credentials'] is not None
