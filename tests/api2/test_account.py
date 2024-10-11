from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_method_calls


def test_create_account_audit():
    user_id = None
    try:
        with expect_audit_method_calls([{
            "method": "user.create",
            "params": [
                {
                    "username": "sergey",
                    "full_name": "Sergey",
                    "group_create": True,
                    "home": "/nonexistent",
                    "password": "********",
                }
            ],
            "description": "Create user sergey",
        }]):
            payload = {
                "username": "sergey",
                "full_name": "Sergey",
                "group_create": True,
                "home": "/nonexistent",
                "password": "password",
            }
            user_id = call("user.create", payload)
    finally:
        if user_id is not None:
            call("user.delete", user_id)


def test_update_account_audit():
    with user({
        "username": "user2",
        "full_name": "user2",
        "group_create": True,
        "password": "test1234",
    }) as u:
        with expect_audit_method_calls([{
            "method": "user.update",
            "params": [u["id"], {}],
            "description": "Update user user2",
        }]):
            call("user.update", u["id"], {})


def test_delete_account_audit():
    with user({
        "username": "user2",
        "full_name": "user2",
        "group_create": True,
        "password": "test1234",
    }) as u:
        with expect_audit_method_calls([{
            "method": "user.delete",
            "params": [u["id"], {}],
            "description": "Delete user user2",
        }]):
            call("user.delete", u["id"], {})


def test_create_group_audit():
    group_id = None
    try:
        with expect_audit_method_calls([{
            "method": "group.create",
            "params": [
                {
                    "name": "group2",
                }
            ],
            "description": "Create group group2",
        }]):
            payload = {
                "name": "group2",
            }
            group_id = call("group.create", payload)
    finally:
        if group_id is not None:
            call("group.delete", group_id)


def test_update_group_audit():
    with group({
        "name": "group2",
    }) as g:
        with expect_audit_method_calls([{
            "method": "group.update",
            "params": [g["id"], {}],
            "description": "Update group group2",
        }]):
            call("group.update", g["id"], {})


def test_delete_group_audit():
    with group({
        "name": "group2",
    }) as g:
        with expect_audit_method_calls([{
            "method": "group.delete",
            "params": [g["id"]],
            "description": "Delete group group2",
        }]):
            call("group.delete", g["id"])


def test_delete_group_audit_delete_users():
    with group({
        "name": "group2",
    }) as g:
        with expect_audit_method_calls([{
            "method": "group.delete",
            "params": [g["id"], {"delete_users": True}],
            "description": "Delete group group2 and all users that have this group as their primary group",
        }]):
            call("group.delete", g["id"], {"delete_users": True})


def test_update_account_using_token():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

        c.call("user.update", 1, {})
