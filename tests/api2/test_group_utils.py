import pytest
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.account import group, user

pytestmark = pytest.mark.accounts


def test_root_password_disabled():
    with group({"name": "group1"}) as g1:
        with group({"name": "group2"}) as g2:
            with user({
                "username": "test",
                "full_name": "Test",
                "group_create": True,
                "groups": [g1["id"], g2["id"]],
                "password": "test1234",
            }) as u:
                result = call("group.get_password_enabled_users", [g1["gid"], g2["gid"]], [])
                assert len(result) == 1
                assert result[0]["id"] == u["id"]
