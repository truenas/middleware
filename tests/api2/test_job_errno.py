import pytest

from middlewared.test.integration.utils import call, mock
from truenas_api_client import ClientException


def test_job_errno():
    with mock("test.test1", """
        from typing import Annotated
        from pydantic import create_model, Field, Secret
        from middlewared.api import api_method
        from middlewared.api.base import BaseModel
        from middlewared.service import job
        from middlewared.service_exception import CallError

        @api_method(
            create_model(
                "MockArgs",
                __base__=(BaseModel,),
            ),
            create_model(
                "MockResult",
                __base__=(BaseModel,),
                result=Annotated[Secret[str], Field()],
            ),
            private=True,
        )
        @job()
        def mock(self, job, *args):
            raise CallError("canary", 13)
    """):
        job_id = call("test.test1")

        with pytest.raises(ClientException):
            call("core.job_wait", job_id, job=True)

        result = call("core.get_jobs", [["id", "=", job_id]], {"get": True})

        assert "errno" in result["exc_info"]
        assert result["exc_info"]["errno"] == 13
