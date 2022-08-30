import errno
import json
import types

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client, mock, ssh


@pytest.fixture(scope="module")
def unprivileged_user():
    with group({
        "name": "unprivileged_users"
    }) as g:
        with privilege({
            "name": "Unprivileged users",
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        }):
            with dataset("unprivileged_homedir") as unprivileged_homedir:
                username = "unprivileged"
                password = "test1234"
                with user({
                    "username": username,
                    "full_name": "Unprivileged user",
                    "group_create": True,
                    "groups": [g["id"]],
                    "home": f"/mnt/{unprivileged_homedir}",
                    "password": password,
                }):
                    yield types.SimpleNamespace(username=username, password=password)


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
