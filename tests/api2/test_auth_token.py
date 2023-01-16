import io
import json

import pytest
import requests

import os
import sys
sys.path.append(os.getcwd())
from functions import GET
from auto_config import ip

from middlewared.test.integration.assets.account import unprivileged_user as unprivileged_user_template
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.shell import assert_shell_works


@pytest.fixture(scope="module")
def download_token():
    return call("auth.generate_token", 300, {"filename": "debug.txz", "job": 1020}, True)


def test_download_auth_token_cannot_be_used_for_restful_api_call(download_token):
    results = GET("/user/id/1/", anonymous=True, headers={"Authorization": f"Token {download_token}"})
    assert results.status_code == 403, results.text


def test_download_auth_token_cannot_be_used_for_upload(download_token):
    r = requests.post(
        f"http://{ip}/_upload",
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
        allowlist=[{"method": "CALL", "resource": "system.info"}],
        web_shell=True,
    ):
        yield


def test_login_with_token_match_origin(unprivileged_user):
    token = ssh(
        "sudo -u test midclt -u ws://localhost/websocket -U test -P test1234 call auth.generate_token 300 '{}' true"
    ).strip()

    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", token)


def test_login_with_token_no_match_origin(unprivileged_user):
    token = ssh(
        "sudo -u test midclt -u ws://localhost/websocket -U test -P test1234 call auth.generate_token 300"
    ).strip()

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)


def test_token_is_for_one_time_use():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", token)
