import json
import time

from middlewared.schema import accepts, Any
from middlewared.service import job, Service


class RestTestService(Service):
    class Config:
        private = True

    @accepts(Any("arg"))
    @job(pipes=["input"])
    def test_input_pipe(self, job, arg):
        return json.dumps(arg) + job.pipes.input.r.read().decode("utf-8")

    @accepts(Any("arg"))
    @job(pipes=["input"], check_pipes=False)
    def test_input_unchecked_pipe(self, job, arg):
        if job.pipes.input:
            input_ = job.pipes.input.r.read().decode("utf-8")
        else:
            input_ = "NONE"

        return json.dumps(arg) + input_

    @accepts(Any("arg"))
    @job(pipes=["output"])
    def test_download_pipe(self, job, arg):
        job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
        job.pipes.output.w.close()

    @accepts(Any("arg"))
    @job(pipes=["output"], check_pipes=False)
    def test_download_unchecked_pipe(self, job, arg):
        if job.pipes.output:
            job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
            job.pipes.output.w.close()
        else:
            return {"wrapped": arg}

    @accepts(Any("arg"))
    @job(pipes=["output"])
    def test_download_slow_pipe(self, job, arg):
        time.sleep(2)
        job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
        job.pipes.output.w.close()

    @accepts(Any("arg"))
    @job(lock="test_download_slow_pipe_with_lock", lock_queue_size=0, pipes=["output"])
    def test_download_slow_pipe_with_lock(self, job, arg):
        time.sleep(5)
        job.pipes.output.w.write(json.dumps(arg).encode("utf-8"))
        job.pipes.output.w.close()
