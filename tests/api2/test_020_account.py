import pytest

from middlewared.test.integration.utils import call


def delete_group_delete_users(delete_users):
    user_id = call("user.create", {
        "username": "test",
        "group_create": True,
        "full_name": "Test",
        "smb": False,
        "password_disabled": True,
    })

    results = call("user.query", [["id", "=", user_id]])
    group_id = results[0]["group"]["id"]

    call("group.delete", group_id, {"delete_users": delete_users})

    return user_id, group_id


@pytest.mark.parametrize("delete_users", [True, False])
def test_delete_group(delete_users):
    user_id, group_id = delete_group_delete_users(delete_users)

    results = call("user.query", [["id", "=", user_id]])
    if delete_users:
        results = call("user.query", [["id", "=", user_id]])
        assert results == []
    else:
        assert results[0]["group"]["bsdgrp_group"] in ["nogroup", "nobody"]
        results = call("user.delete", user_id)
