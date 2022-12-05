import errno
import json
import logging

import pytest
import websocket

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import user, unprivileged_user as unprivileged_user_template
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client, ssh, websocket_url
from middlewared.test.integration.utils.shell import assert_shell_works

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def unprivileged_user():
    with unprivileged_user_template(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        allowlist=[{"method": "CALL", "resource": "system.info"}],
        web_shell=False,
    ) as t:
        yield t


@pytest.fixture()
def unprivileged_user_token(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        return c.call("auth.generate_token", 300, {}, True)


@pytest.fixture(scope="module")
def unprivileged_user_with_web_shell():
    with unprivileged_user_template(
        username="unprivilegedws",
        group_name="unprivileged_users_ws",
        privilege_name="Unprivileged users with web shell",
        allowlist=[],
        web_shell=True,
    ) as t:
        yield t


@pytest.fixture()
def unprivileged_user_with_web_shell_token(unprivileged_user_with_web_shell):
    with client(auth=(unprivileged_user_with_web_shell.username, unprivileged_user_with_web_shell.password)) as c:
        return c.call("auth.generate_token", 300, {}, True)


def test_websocket_auth_session_list_terminate(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        sessions = call("auth.sessions")
        my_sessions = [
            s for s in sessions
            if s["credentials"] == "LOGIN_PASSWORD" and s["credentials_data"]["username"] == unprivileged_user.username
        ]
        assert len(my_sessions) == 1, sessions

        call("auth.terminate_session", my_sessions[0]["id"])

        with pytest.raises(Exception):
            c.call("system.info")

    sessions = call("auth.sessions")
    assert not [
        s for s in sessions
        if s["credentials"] == "LOGIN_PASSWORD" and s["credentials_data"]["username"] == unprivileged_user.username
    ], sessions


def test_websocket_auth_terminate_all_other_sessions(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        call("auth.terminate_other_sessions")

        with pytest.raises(Exception):
            c.call("system.info")


def test_websocket_auth_get_methods(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        methods = c.call("core.get_methods")

    assert "system.info" in methods
    assert "pool.create" not in methods


def test_websocket_auth_calls_allowed_method(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        c.call("system.info")


def test_websocket_auth_fails_to_call_forbidden_method(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        with pytest.raises(ClientException) as ve:
            c.call("pool.create")

        assert ve.value.errno == errno.EACCES


def test_unix_socket_auth_get_methods(unprivileged_user):
    methods = json.loads(ssh(f"sudo -u {unprivileged_user.username} midclt call core.get_methods"))

    assert "system.info" in methods
    assert "pool.create" not in methods


def test_unix_socket_auth_calls_allowed_method(unprivileged_user):
    ssh(f"sudo -u {unprivileged_user.username} midclt call system.info")


def test_unix_socket_auth_fails_to_call_forbidden_method(unprivileged_user):
    result = ssh(f"sudo -u {unprivileged_user.username} midclt call pool.create", check=False, complete_response=True)
    assert "Not authorized" in result["stderr"]


def test_unix_socket_auth_fails_when_user_has_no_privilege():
    with dataset(f"noconnect_homedir") as homedir:
        with user({
            "username": "noconnect",
            "full_name": "Noconnect",
            "group_create": True,
            "groups": [],
            "home": f"/mnt/{homedir}",
            "password": "test1234",
        }):
            result = ssh(f"sudo -u noconnect midclt call pool.create", check=False, complete_response=True)
            assert "Not authenticated" in result["stderr"]


def test_token_auth_session_list_terminate(unprivileged_user, unprivileged_user_token):
    with client(auth=None) as c:
        assert c.call("auth.login_with_token", unprivileged_user_token)

        sessions = call("auth.sessions")
        my_sessions = [
            s for s in sessions
            if (
                s["credentials"] == "TOKEN" and
                s["credentials_data"]["parent"]["credentials"] == "LOGIN_PASSWORD" and
                s["credentials_data"]["parent"]["credentials_data"]["username"] == unprivileged_user.username
            )
        ]
        assert len(my_sessions) == 1, sessions

        call("auth.terminate_session", my_sessions[0]["id"])

        with pytest.raises(Exception):
            c.call("system.info")


def test_token_auth_calls_allowed_method(unprivileged_user_token):
    with client(auth=None) as c:
        assert c.call("auth.login_with_token", unprivileged_user_token)

        c.call("system.info")


def test_token_auth_fails_to_call_forbidden_method(unprivileged_user_token):
    with client(auth=None) as c:
        assert c.call("auth.login_with_token", unprivileged_user_token)

        with pytest.raises(ClientException) as ve:
            c.call("pool.create")

        assert ve.value.errno == errno.EACCES


def test_drop_privileges(unprivileged_user_token):
    with client() as c:
        # This should drop privileges for the current root session
        assert c.call("auth.login_with_token", unprivileged_user_token)

        with pytest.raises(ClientException) as ve:
            c.call("pool.create")

        assert ve.value.errno == errno.EACCES


def test_token_auth_working_not_working_web_shell(unprivileged_user_token):
    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.send(json.dumps({"token": unprivileged_user_token}))
        resp_opcode, msg = ws.recv_data()
        assert json.loads(msg.decode())["msg"] == "failed"
    finally:
        ws.close()


@pytest.mark.timeout(30)
def test_token_auth_working_web_shell(unprivileged_user_with_web_shell_token):
    assert_shell_works(unprivileged_user_with_web_shell_token, "unprivilegedws")
