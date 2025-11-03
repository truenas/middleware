import io
import json

from middlewared.test.integration.utils import client, mock, session, url


def test_upload_to_upload_endpoint():
    with session() as s:
        r = s.post(
            f"{url()}/_upload",
            files={
                "data": (None, io.StringIO(json.dumps({
                    "method": "test.test_input_pipe",
                    "params": [{"key": "value"}]
                }))),
                "file": (None, io.StringIO("FILE")),
            },
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]

    with client() as c:
        assert c.call("core.job_wait", job_id, job=True) == '{"key": "value"}FILE'


def test_upload_multiple_files():
    with mock("test.test1", """    
        from middlewared.service import job

        @job(pipes=["input"])
        def mock(self, job, *args):
            return "".join([pipe.r.read().decode() for pipe in job.pipes.inputs])
    """):
        with session() as s:
            r = s.post(
                f"{url()}/_upload",
                files=[
                    ("data", (None, io.StringIO(json.dumps({
                        "method": "test.test1",
                        "params": []
                    })))),
                    ("file", (None, io.StringIO("FILE1"))),
                    ("file", (None, io.StringIO("FILE2"))),
                    ("file", (None, io.StringIO("FILE3"))),
                ],
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]

        with client() as c:
            assert c.call("core.job_wait", job_id, job=True) == 'FILE1FILE2FILE3'


def test_upload_multiple_files_job_does_not_consume_completely():
    with mock("test.test1", """    
        from middlewared.service import job

        @job(pipes=["input"])
        def mock(self, job, *args):
            return "".join([pipe.r.read(2).decode() for pipe in job.pipes.inputs])
    """):
        with session() as s:
            r = s.post(
                f"{url()}/_upload",
                files=[
                    ("data", (None, io.StringIO(json.dumps({
                        "method": "test.test1",
                        "params": []
                    })))),
                    ("file", (None, io.StringIO("ABCD" * 1000000))),
                    ("file", (None, io.StringIO("EFGH" * 1000000))),
                ],
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]

        with client() as c:
            assert c.call("core.job_wait", job_id, job=True) == 'ABEF'
