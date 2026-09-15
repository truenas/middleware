import errno
import threading
import time

import pytest
import requests

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.utils import call, client, url

ARG = {"key": "value"}
PAYLOAD = '{"key": "value"}'


def test_download_from_download_endpoint():
    with client() as c:
        job_id, path = c.call("core.download", "test.test_download_pipe", [{"key": "value"}], "file.bin")

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
        job_id, path = c.call("core.download", "test.test_download_slow_pipe", [{"key": "value"}], "file.bin",
                              buffered)

    time.sleep(sleep)

    r = requests.get(f"{url()}{path}")
    r.raise_for_status()

    assert r.headers["Content-Disposition"] == "attachment; filename=\"file.bin\""
    assert r.headers["Content-Type"] == "application/octet-stream"
    assert r.text == result


def test_download_duplicate_job():
    call("core.download", "test.test_download_slow_pipe_with_lock", [{"key": "value"}], "file.bin")
    with pytest.raises(CallError) as ve:
        call("core.download", "test.test_download_slow_pipe_with_lock", [{"key": "value"}], "file.bin")

    assert ve.value.errno == errno.EBUSY


def test_download_authorization_ok():
    with unprivileged_user(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        roles=["FULL_ADMIN"],
        web_shell=False,
    ) as user:
        with client(auth=(user.username, user.password)) as c:
            c.call("core.download", "test.test_download_slow_pipe", [{"key": "value"}], "file.bin")


def test_download_authorization_fails():
    with unprivileged_user(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        roles=["READONLY_ADMIN"],
        web_shell=False,
    ) as user:
        with client(auth=(user.username, user.password)) as c:
            with pytest.raises(CallError) as ve:
                c.call("core.download", "test.test_download_slow_pipe", [{"key": "value"}], "file.bin")

            assert ve.value.errno == errno.EACCES


def wait_for_job_state(job_id, *states, timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
        if job["state"] in states:
            return job

        if time.monotonic() >= deadline:
            raise AssertionError(f"Job {job_id} is {job['state']!r}, expected one of {states!r}")

        time.sleep(0.1)


def download(path):
    return requests.get(f"{url()}{path}", timeout=120)


def test_download_successful_job():
    job_id, path = call("core.download", "test.test_download_pipe", [ARG], "file.bin")
    wait_for_job_state(job_id, "SUCCESS")

    r = download(path)

    assert r.status_code == 200
    assert r.text == PAYLOAD


def test_download_failed_job():
    job_id, path = call("core.download", "test.test_download_failing_pipe", [ARG], "file.bin")
    wait_for_job_state(job_id, "FAILED")

    r = download(path)

    assert r.status_code == 422
    assert PAYLOAD in r.text


def test_download_job_that_fails_while_being_downloaded():
    """The download is requested while the job is still running and only fails afterwards."""
    job_id, path = call("core.download", "test.test_download_slow_failing_pipe", [ARG], "file.bin")

    r = download(path)

    assert r.status_code == 422
    assert PAYLOAD in r.text
    assert call("core.get_jobs", [["id", "=", job_id]], {"get": True})["state"] == "FAILED"


def test_download_failed_job_that_produced_partial_output():
    """Output written by a job that failed afterwards is incomplete and must not be served as a successful download."""
    job_id, path = call("core.download", "test.test_download_failing_pipe_with_partial_output", [ARG], "file.bin",
                        True)
    wait_for_job_state(job_id, "FAILED")

    r = download(path)

    assert r.status_code == 422
    assert PAYLOAD in r.text


def test_download_aborted_job():
    job_id, path = call("core.download", "test.test_download_abortable_pipe", [ARG], "file.bin")
    call("core.job_abort", job_id)
    wait_for_job_state(job_id, "ABORTED")

    r = download(path)

    assert r.status_code == 422
    assert f"Job {job_id} was aborted" in r.text


def test_download_job_that_is_aborted_while_being_downloaded():
    """The download is requested while the job is still running and it is only aborted afterwards."""
    job_id, path = call("core.download", "test.test_download_abortable_pipe", [ARG], "file.bin")

    abort = threading.Timer(2, lambda: call("core.job_abort", job_id))
    abort.start()
    try:
        r = download(path)
    finally:
        abort.cancel()

    assert r.status_code == 422
    assert f"Job {job_id} was aborted" in r.text


@pytest.mark.parametrize("method", ["test.test_download_failing_pipe", "test.test_download_abortable_pipe"])
def test_download_token_is_still_single_use(method):
    """A failed download must not leave a reusable download token behind."""
    job_id, path = call("core.download", method, [ARG], "file.bin")
    if method.endswith("abortable_pipe"):
        call("core.job_abort", job_id)

    assert download(path).status_code == 422
    assert download(path).status_code == 401
