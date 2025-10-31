import json
import time
from typing import Any

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.service import job, Service


class TestArgs(BaseModel):
    arg: Any


class TestResult(BaseModel):
    result: Any


class TestService(Service):
    class Config:
        private = True

    @api_method(TestArgs, TestResult, authorization_required=False)
    @job(pipes=["input"])
    def test_input_pipe(self, job, arg):
        return json.dumps(arg) + job.pipes.input.r.read().decode("utf-8")

    @api_method(TestArgs, TestResult, authorization_required=False)
    @job(pipes=["output"])
    def test_download_pipe(self, job, arg):
        job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
        job.pipes.output.w.close()

    @api_method(TestArgs, TestResult, authorization_required=False)
    @job(pipes=["output"])
    def test_download_slow_pipe(self, job, arg):
        time.sleep(2)
        job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
        job.pipes.output.w.close()

    @api_method(TestArgs, TestResult, authorization_required=False)
    @job(lock="test_download_slow_pipe_with_lock", lock_queue_size=0, pipes=["output"])
    def test_download_slow_pipe_with_lock(self, job, arg):
        time.sleep(5)
        job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
        job.pipes.output.w.close()
