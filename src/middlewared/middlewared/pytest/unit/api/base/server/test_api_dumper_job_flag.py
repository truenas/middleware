import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.server.doc import APIDumper
from middlewared.service import job


class JobFlagTestArgs(BaseModel):
    name: str


class JobFlagTestResult(BaseModel):
    result: bool


class FakeMethod:
    def __init__(self, methodobj, name="test.method"):
        self.name = name
        self.methodobj = methodobj

    async def accepts_model(self):
        return JobFlagTestArgs

    async def returns_model(self):
        return JobFlagTestResult


class FakeRoleManager:
    def atomic_roles_for_method(self, name):
        return {"READONLY_ADMIN"}


def make_dumper():
    return APIDumper("v1.0", "v1.0 (current)", api=None, role_manager=FakeRoleManager())


@pytest.mark.asyncio
async def test_non_job_method():
    async def plain_method(self, data):
        """Do something."""

    dump = await make_dumper()._dump_method(FakeMethod(plain_method))

    assert dump.job is False
    assert dump.input_pipes is False
    assert dump.output_pipes is False
    assert dump.check_pipes is True
    assert "This method is a job." not in dump.doc


@pytest.mark.asyncio
async def test_job_method():
    @job()
    async def job_method(self, job_, data):
        """Do something."""

    dump = await make_dumper()._dump_method(FakeMethod(job_method))

    assert dump.job is True
    assert dump.input_pipes is False
    assert dump.output_pipes is False
    assert dump.check_pipes is True
    # The doc text is still appended for the docs builder.
    assert dump.doc.endswith("This method is a job.")


@pytest.mark.asyncio
async def test_job_method_with_pipes():
    @job(pipes=["input", "output"], check_pipes=False)
    async def pipes_method(self, job_, data):
        """Do something."""

    dump = await make_dumper()._dump_method(FakeMethod(pipes_method))

    assert dump.job is True
    assert dump.input_pipes is True
    assert dump.output_pipes is True
    assert dump.check_pipes is False
