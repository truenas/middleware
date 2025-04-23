import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import user, group, unprivileged_user_client
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_method_calls

BASE_SYNTHETIC_DATASTORE_ID = 100000000
DS_USR_VERR_STR = "Directory services users may not be added as members of local groups."
DS_GRP_VERR_STR = "Local users may not be members of directory services groups."


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
            user_id = call("user.create", payload)['id']
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


@pytest.mark.parametrize("roles, message", [
    (["FULL_ADMIN"], "Cannot delete the currently active user"),
    (["SHARING_ADMIN"], "Not authorized")
])
def test_delete_self(roles, message):
    with unprivileged_user_client(roles) as c:
        user_id = c.call("user.query", [["username", "=", c.username]], {"get": True})["id"]
        with pytest.raises(CallError, match=message):
            c.call("user.delete", user_id)


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


def test_create_local_group_ds_user():
    with pytest.raises(ValidationErrors) as ve:
        with group({"name": "local_ds", "users": [BASE_SYNTHETIC_DATASTORE_ID + 1]}):
            pass

    assert DS_USR_VERR_STR in str(ve)


def test_create_local_user_ds_group():
    with pytest.raises(ValidationErrors) as ve:
        with user({
            "username": "local_ds",
            "groups": [BASE_SYNTHETIC_DATASTORE_ID + 1],
            "full_name": "user_ds",
            "group_create": True,
            "password": "test1234",
        }):
            pass

    assert DS_GRP_VERR_STR in str(ve)


def test_create_account_invalid_gid():
    with pytest.raises(ValidationErrors) as ve:
        with user({
            "username": "invalid_user",
            "groups": [BASE_SYNTHETIC_DATASTORE_ID - 1],
            "full_name": "invalid_user",
            "group_create": True,
            "password": "test1234",
        }):
            pass

    assert "This group does not exist." in str(ve)


def test_create_user_random_password_with_specified_password_fail():
    with pytest.raises(ValidationErrors, match='Requesting a randomized password while') as ve:
        with user({
            "username": "bobshouldnotexist",
            "full_name": "bob",
            "group_create": True,
            "password": "test1234",
            "random_password": True
        }):
            pass


def test_create_user_with_random_password():
    with user({
        "username": "bobrandom",
        "full_name": "bob",
        "group_create": True,
        "random_password": True
    }, get_instance=True) as u:
        assert u['password']


def test_update_user_with_random_password():
    with user({
        "username": "bobrandom",
        "full_name": "bob",
        "group_create": True,
        "password": "canary"
    }, get_instance=True) as u:
        assert u['password'] == 'canary'

        new = call('user.update', u['id'], {'random_password': True})
        assert new['password'] != 'canary'

        new = call('user.update', u['id'], {'full_name': 'bob2'})
        assert not new['password']


def test_account_create_invalid_username():
    with pytest.raises(ValidationErrors, match="Valid characters are:"):
        with user({
            "username": "_блин",
            "full_name": "bob",
            "group_create": True,
            "password": "canary"
        }):
            pass


def test_account_update_invalid_username():
    with user({
        "username": "bob",
        "full_name": "bob",
        "group_create": True,
        "password": "canary"
    }, get_instance=True) as u:
        with pytest.raises(ValidationErrors, match="Valid characters are:"):
            call("user.update", u["id"], {"username": "_блин"})
