import contextlib
import errno
import json
import logging
import re
import time
import types

import pytest
import websocket

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client, mock, ssh, websocket_url

logger = logging.getLogger(__name__)

ansi_escape_8bit = re.compile(br"(?:\x1B[<-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[<-~])")


@contextlib.contextmanager
def unprivileged_user_template(*, username, group_name, privilege_name, web_shell):
    with group({
        "name": group_name,
    }) as g:
        with privilege({
            "name": privilege_name,
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": web_shell,
        }):
            with dataset(f"{username}_homedir") as homedir:
                if web_shell:
                    # To prevent `zsh-newuser-install` interactive prompt
                    ssh(f"touch /mnt/{homedir}/.zshrc")

                password = "test1234"
                with user({
                    "username": username,
                    "full_name": "Unprivileged user",
                    "group_create": True,
                    "groups": [g["id"]],
                    "home": f"/mnt/{homedir}",
                    "password": password,
                }):
                    yield types.SimpleNamespace(username=username, password=password)


@pytest.fixture(scope="module")
def unprivileged_user():
    with unprivileged_user_template(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        web_shell=False,
    ) as t:
        yield t


@pytest.fixture()
def unprivileged_user_token(unprivileged_user):
    with client(auth=(unprivileged_user.username, unprivileged_user.password)) as c:
        return c.call("auth.generate_token")


@pytest.fixture(scope="module")
def unprivileged_user_with_web_shell():
    with unprivileged_user_template(
        username="unprivilegedws",
        group_name="unprivileged_users_ws",
        privilege_name="Unprivileged users with web shell",
        web_shell=True,
    ) as t:
        yield t


@pytest.fixture()
def unprivileged_user_with_web_shell_token(unprivileged_user_with_web_shell):
    with client(auth=(unprivileged_user_with_web_shell.username, unprivileged_user_with_web_shell.password)) as c:
        return c.call("auth.generate_token")


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
    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.send(json.dumps({"token": unprivileged_user_with_web_shell_token}))
        resp_opcode, msg = ws.recv_data()
        assert json.loads(msg.decode())["msg"] == "connected"

        for i in range(60):
            resp_opcode, msg = ws.recv_data()
            msg = ansi_escape_8bit.sub(b"", msg).decode("ascii")
            logger.debug("Received 1 %r", msg)
            if msg.endswith("% "):  # ZSH prompt
                break

        ws.send_binary(b"whoami\n")

        for i in range(60):
            resp_opcode, msg = ws.recv_data()
            msg = ansi_escape_8bit.sub(b"", msg).decode("ascii")
            logger.debug("Received 2 %r", msg)
            if "unprivilegedws" in msg.split():
                break
    finally:
        ws.close()
        # Give middleware time to kill user's zsh on connection close (otherwise, it will prevent user's home directory
        # dataset from being destroyed)
        time.sleep(5)
