import io
import json

import pytest
from functions import http_post

from middlewared.test.integration.assets.account import unprivileged_user as unprivileged_user_template
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.shell import assert_shell_works
from middlewared.service_exception import CallError


@pytest.fixture(scope="module")
def job_with_pipe():
    job_id, url = call("core.download", "config.save" , [], "debug.txz")
    try:
        yield job_id
    finally:
        call("core.job_abort", job_id)


@pytest.fixture(scope="module")
def download_token(job_with_pipe):
    return call("auth.generate_token", 300, {"filename": "debug.txz", "job": job_with_pipe}, True)


def test_download_auth_token_cannot_be_used_for_upload(download_token):
    r = http_post(
        f"http://{truenas_server.ip}/_upload",
        headers={"Authorization": f"Token {download_token}"},
        data={
            "data": json.dumps({
                "method": "filesystem.put",
                "params": ["/tmp/upload"],
            })
        },
        files={
            "file": io.BytesIO(b"test"),
        },
        timeout=10
    )
    assert r.status_code == 403


def test_download_auth_token_cannot_be_used_for_websocket_auth(download_token):
    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", download_token)


@pytest.mark.timeout(30)
def test_token_created_by_token_can_use_shell():
    with client() as c:
        token = c.call("auth.generate_token", 300, {}, True)

        with client(auth=None) as c2:
            assert c2.call("auth.login_with_token", token)

            token2 = c2.call("auth.generate_token", 300, {}, True)
            assert_shell_works(token2, "root")


@pytest.fixture(scope="module")
def unprivileged_user():
    with unprivileged_user_template(
        username="test",
        group_name="test",
        privilege_name="test",
        roles=['READONLY_ADMIN'],
        web_shell=True,
    ):
        yield


def test_login_with_token_match_origin(unprivileged_user):
    token = ssh(
        "sudo -u test midclt -u ws://localhost/api/current -U test -P test1234 call auth.generate_token 300 '{}' true"
    ).strip()

    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", token)


def test_login_with_token_no_match_origin(unprivileged_user):
    token = ssh(
        "sudo -u test midclt -u ws://localhost/api/current -U test -P test1234 call auth.generate_token 300 '{}' false"
    ).strip()

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)


def test_token_is_for_one_time_use():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", token)


def test_kill_all_tokens_on_session_termination():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

        token = c.call("auth.generate_token")

        session = c.call("auth.sessions", [["current", "=", True]], {"get": True})
        call("auth.terminate_session", session["id"])

        with client(auth=None) as c:
            assert not c.call("auth.login_with_token", token)


def test_single_use_token():
    token = call("auth.generate_token", 300, {}, True, True)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)
        assert not c.call("auth.login_with_token", token)


def test_token_job_validation(job_with_pipe):
    with pytest.raises(CallError, match='job does not exist'):
        call("auth.generate_token", 300, {'job': -1})

    with unprivileged_user_client(roles=['READONLY_ADMIN']) as c:
        with pytest.raises(CallError, match='Job is not owned by current session'):
            c.call("auth.generate_token", 300, {'job': job_with_pipe})
