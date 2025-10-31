import errno
import time

import pytest
import requests

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.utils import call, client, url


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
