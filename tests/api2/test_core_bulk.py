from unittest.mock import ANY

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, mock
from middlewared.test.integration.utils.audit import expect_audit_log
from truenas_api_client import ClientException


def test_core_bulk_reports_job_id():
    with mock("test.test1", """\
        from middlewared.service import job, CallError

        @job()
        def mock(self, job, *args):
            if args[0] == 0:
                raise CallError("Error")
            else:
                return args[0]
    """):
        result = call("core.bulk", "test.test1", [[0], [10]], job=True)

        assert result == [
            {"job_id": ANY, "result": None, "error": "[EFAULT] Error"},
            {"job_id": ANY, "result": 10, "error": None},
        ]

        job_0 = call("core.get_jobs", [["id", "=", result[0]["job_id"]]], {"get": True})
        assert job_0["arguments"] == [0]
        job_1 = call("core.get_jobs", [["id", "=", result[1]["job_id"]]], {"get": True})
        assert job_1["arguments"] == [10]


def test_authorized():
    with unprivileged_user_client(allowlist=[{"method": "CALL", "resource": "test.test1"}]) as c:
        with mock("test.test1", """
            from middlewared.service import pass_app

            @pass_app()
            async def mock(self, app):
                return app.authenticated_credentials.dump()["username"].startswith("unprivileged")
        """):
            assert c.call("core.bulk", "test.test1", [[]], job=True) == [{"result": True, "error": None}]


def test_authorized_audit():
    with unprivileged_user_client(allowlist=[{"method": "CALL", "resource": "test.test1"}]) as c:
        with mock("test.test1", """
            from middlewared.schema import Int
            from middlewared.service import accepts

            @accepts(Int("param"), audit="Mock", audit_extended=lambda param: str(param))
            async def mock(self, param):
                return 
        """):
            with expect_audit_log([
                {
                    "event": "METHOD_CALL",
                    "event_data": {
                        "authenticated": True,
                        "authorized": True,
                        "method": "test.test1",
                        "params": [42],
                        "description": "Mock 42",
                    },
                    "success": True,
                }
            ]):
                c.call("core.bulk", "test.test1", [[42]], job=True)


def test_not_authorized():
    with unprivileged_user_client(allowlist=[]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("core.bulk", "test.test1", [[]], job=True)

        assert ve.value.error == "[EPERM] Not authorized"


def test_not_authorized_audit():
    with unprivileged_user_client() as c:
        with expect_audit_log([
            {
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": True,
                    "authorized": False,
                    "method": "user.create",
                    "params": [{"username": "sergey", "full_name": "Sergey"}],
                    "description": "Create user sergey",
                },
                "success": False,
            }
        ]):
            with pytest.raises(ClientException):
                c.call("core.bulk", "user.create", [[{"username": "sergey", "full_name": "Sergey"}]], job=True)
