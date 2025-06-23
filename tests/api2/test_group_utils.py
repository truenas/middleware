import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.account import group, user


@pytest.fixture(scope="module")
def temp_groups():
    with (
        group({"name": "group1"}) as g1,
        group({"name": "group2"}) as g2,
    ):
        yield g1, g2


def test_get_password_enabled_users(temp_groups):
    g1, g2 = temp_groups
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


def test_get_password_enabled_users_primary_group(temp_groups):
    g1, _ = temp_groups
    with (
        user({
            "username": "test1",
            "full_name": "Test1",
            "group": g1["id"],
            "password": "test1234",
        }) as u1,
        user({
            "username": "test2",
            "full_name": "Test2",
            "group": g1["id"],
            "password": "test1234",
        }) as u2,
        user({
            "username": "test3",
            "full_name": "Test3",
            "group": g1["id"],
            "password_disabled": True,  # should not be in result
            "smb": False,
        }),
    ):
        # Exclude u1 from result
        result = call("group.get_password_enabled_users", [g1["gid"]], [u1["id"]])
    assert len(result) == 1
    assert result[0]["id"] == u2["id"]
