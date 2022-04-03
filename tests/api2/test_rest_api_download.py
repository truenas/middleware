import time

import pytest
import requests

from middlewared.test.integration.utils import client, session, url


@pytest.mark.parametrize("method", ["test_download_pipe", "test_download_unchecked_pipe"])
def test_download(method):
    with session() as s:
        r = s.post(
            f"{url()}/api/v2.0/resttest/{method}",
            headers={"Content-type": "application/json"},
            data="{\"key\": \"value\"}",
        )
        r.raise_for_status()
        assert r.headers["Content-Type"] == "application/octet-stream"
        assert r.text == '{"key": "value"}'


def test_no_download_from_checked_pipe():
    with session() as s:
        r = s.post(
            f"{url()}/api/v2.0/resttest/test_download_pipe?download=0",
            headers={"Content-type": "application/json"},
            data="{\"key\": \"value\"}",
        )

        assert r.status_code == 400
        assert r.json()["message"] == "JSON response is not supported for this method."


def test_no_download_from_unchecked_pipe():
    with session() as s:
        r = s.post(
            f"{url()}/api/v2.0/resttest/test_download_unchecked_pipe?download=0",
            headers={"Content-type": "application/json"},
            data="{\"key\": \"value\"}",
        )
        r.raise_for_status()

        assert r.headers["Content-Type"].startswith("application/json")
        assert r.json() == {"wrapped": {"key": "value"}}


def test_download_from_download_endpoint():
    with client() as c:
        job_id, path = c.call("core.download", "resttest.test_download_pipe", [{"key": "value"}], "file.bin")

    r = requests.get(f"{url()}{path}")
    r.raise_for_status()

    assert r.headers["Content-Disposition"] == "attachment; filename=\"file.bin\""
    assert r.headers["Content-Type"] == "application/octet-stream"
    assert r.text == '{"key": "value"}'


@pytest.mark.parametrize("buffered,sleep,result", [
    (True, 0, ""),
    (True, 4, '{"key": "value"}'),
    (False, 0, '{"key": "value"}'),
])
def test_buffered_download_from_slow_download_endpoint(buffered, sleep, result):
    with client() as c:
        job_id, path = c.call("core.download", "resttest.test_download_slow_pipe", [{"key": "value"}], "file.bin",
                              buffered)

    time.sleep(sleep)

    r = requests.get(f"{url()}{path}")
    r.raise_for_status()

    assert r.headers["Content-Disposition"] == "attachment; filename=\"file.bin\""
    assert r.headers["Content-Type"] == "application/octet-stream"
    assert r.text == result
