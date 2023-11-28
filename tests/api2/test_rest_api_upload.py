import io
import json

import pytest

from middlewared.test.integration.utils import client, session, url


@pytest.mark.parametrize("method", ["test_input_pipe", "test_input_unchecked_pipe"])
def test_upload(method):
    with session() as s:
        r = s.post(
            f"{url()}/api/v2.0/resttest/{method}",
            files={
                "data": (None, io.StringIO('{"key": "value"}')),
                "file": (None, io.StringIO("FILE")),
            },
        )
        r.raise_for_status()
        job_id = r.json()

    with client() as c:
        assert c.call("core.job_wait", job_id, job=True) == '{"key": "value"}FILE'


def test_no_upload_to_checked_pipe():
    with session() as s:
        r = s.post(
            f"{url()}/api/v2.0/resttest/test_input_pipe",
            headers={"Content-type": "application/json"},
            data="{\"key\": \"value\"}",
        )

        assert r.status_code == 400
        assert r.json()["message"] == "This method accepts only multipart requests."


def test_no_upload_to_unchecked_pipe():
    with session() as s:
        r = s.post(
            f"{url()}/api/v2.0/resttest/test_input_unchecked_pipe",
            headers={"Content-type": "application/json"},
            data='{"key": "value"}',
        )
        r.raise_for_status()
        job_id = r.json()

    with client() as c:
        assert c.call("core.job_wait", job_id, job=True) == '{"key": "value"}NONE'


def test_upload_to_upload_endpoint():
    with session() as s:
        r = s.post(
            f"{url()}/_upload",
            files={
                "data": (None, io.StringIO(json.dumps({
                    "method": "resttest.test_input_pipe",
                    "params": [{"key": "value"}]
                }))),
                "file": (None, io.StringIO("FILE")),
            },
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]

    with client() as c:
        assert c.call("core.job_wait", job_id, job=True) == '{"key": "value"}FILE'
