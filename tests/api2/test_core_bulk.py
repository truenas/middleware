#!/usr/bin/env python3
from unittest.mock import ANY

from middlewared.test.integration.utils import call, mock


def test_core_bulk_reports_job_id(request):
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
