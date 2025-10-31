import io
import json

from middlewared.test.integration.utils import client, session, url


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
