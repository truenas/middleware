import pytest

from middlewared.test.integration.utils import call, client, mock, ssh


def test_private_params_do_not_leak_to_logs():
    with mock("test.test1", """
        from typing import Annotated
        from pydantic import create_model, Field, Secret
        from middlewared.api import api_method
        from middlewared.api.base import BaseModel

        @api_method(
            create_model(
                "MockArgs",
                __base__=(BaseModel,),
                args=Annotated[
                    create_model(
                        "MockArgsDict",
                        __base__=(BaseModel,),
                        password=Annotated[Secret[str], Field()],
                    ),
                    Field(),
                ],
            ),
            create_model(
                "MockResult",
                __base__=(BaseModel,),
                result=Annotated[int, Field()],
            ),
            private=True,
        )
        async def mock(self, args):
            raise Exception()
    """):
        log_before = ssh("cat /var/log/middlewared.log")

        with client(py_exceptions=False) as c:
            with pytest.raises(Exception):
                c.call("test.test1", {"password": "secret"})

        log = ssh("cat /var/log/middlewared.log")[len(log_before):]
        assert "Exception while calling test.test1(*[{'password': '********'}])" in log


def test_private_params_do_not_leak_to_core_get_jobs():
    with mock("test.test1", """
        from typing import Annotated
        from pydantic import create_model, Field, Secret
        from middlewared.api import api_method
        from middlewared.api.base import BaseModel
        from middlewared.service import job

        @api_method(
            create_model(
                "MockArgs",
                __base__=(BaseModel,),
                args=Annotated[
                    create_model(
                        "MockArgsDict",
                        __base__=(BaseModel,),
                        password=Annotated[Secret[str], Field()],
                    ),
                    Field(),
                ],
            ),
            create_model(
                "MockResult",
                __base__=(BaseModel,),
                result=Annotated[int, Field()],
            ),
            private=True,
        )
        @job()
        async def mock(self, job, args):
            return 42
    """):
        job_id = call("test.test1", {"password": "secret"})

        job_descr = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
        assert job_descr["arguments"] == [{"password": "********"}]
