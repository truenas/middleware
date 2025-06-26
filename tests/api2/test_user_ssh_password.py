import pytest

from auto_config import pool_name
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user, group, temporary_update
from middlewared.test.integration.utils import call, ssh


NO_LOGIN_SHELL = "/usr/sbin/nologin"
HOME_DIR = f"/mnt/{pool_name}"


@pytest.mark.parametrize("ssh_password_enabled", [True, False])
def test_user_ssh_password_enabled(ssh_password_enabled):
    with user({
        "username": "test",
        "full_name": "Test",
        "group_create": True,
        "password": "test1234",
        "home": f"/mnt/{pool_name}",
        "ssh_password_enabled": ssh_password_enabled,
    }):
        result = ssh("whoami", check=False, complete_response=True, user="test",
                     password="test1234")
        if ssh_password_enabled:
            assert "test" in result["output"]
        else:
            assert "Permission denied" in result["stderr"]


@pytest.fixture(scope="module")
def group1_with_user():
    with group({"name": "group1"}) as g1:
        with user({
            "username": "test",
            "full_name": "Test",
            "group_create": True,
            "groups": [g1["id"]],
            "password": "test1234",
        }):
            yield


@pytest.mark.parametrize("ssh_password_enabled", [True, False])
def test_group_ssh_password_enabled(group1_with_user, ssh_password_enabled):
    call("ssh.update", {"password_login_groups": ["group1"] if ssh_password_enabled else []})

    result = ssh("whoami", check=False, complete_response=True, user="test",
                 password="test1234")
    if ssh_password_enabled:
        assert "test" in result["output"]
    else:
        assert "Permission denied" in result["stderr"]


@pytest.mark.parametrize("args, errmsg", [
    (
        {"ssh_password_enabled": True},
        "SSH password login requires a valid home path."
    ),
    (
        {"ssh_password_enabled": True, "home": HOME_DIR, "shell": NO_LOGIN_SHELL},
        "SSH password login requires a login shell."
    ),
    (
        {"ssh_password_enabled": True, "home": HOME_DIR},
        None
    ),
])
def test_user_create_ssh_password_login(args: dict, errmsg: str | None):
    if errmsg is None:
        with user({
            "username": "bob",
            "full_name": "bob",
            "group_create": True,
            "password": "canary",
            **args
        }):
            return
    with pytest.raises(ValidationErrors, match=errmsg):
        with user({
            "username": "bob",
            "full_name": "bob",
            "group_create": True,
            "password": "canary",
            **args
        }):
            pass


@pytest.mark.parametrize("args, errmsg", [
    # When test begins: ssh_password_enabled=False, home is invalid, shell is valid.
    (
        {"ssh_password_enabled": True},
        "Cannot be enabled without a valid home path and login shell."
    ),
    (
        {"ssh_password_enabled": True, "home": "/var/empty"},
        "SSH password login requires a valid home path."
    ),
    (
        {"ssh_password_enabled": True, "shell": NO_LOGIN_SHELL},
        "SSH password login requires a login shell."
    ),
    (
        {"ssh_password_enabled": True, "home": HOME_DIR, "home_create": True},
        None
    ),
])
def test_user_update_ssh_password_login(test_user: dict, args: dict, errmsg: str | None):
    if errmsg is None:
        with temporary_update(test_user, args):
            return
    with pytest.raises(ValidationErrors, match=errmsg):
        with temporary_update(test_user, args):
            pass
