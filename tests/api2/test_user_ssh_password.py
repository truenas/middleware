import pytest

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.utils import call, ssh

pytestmark = pytest.mark.accounts


@pytest.mark.parametrize("ssh_password_enabled", [True, False])
def test_user_ssh_password_enabled(ssh_password_enabled):
    with user({
        "username": "test",
        "full_name": "Test",
        "group_create": True,
        "home": f"/nonexistent",
        "password": "test1234",
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
            "home": f"/nonexistent",
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
