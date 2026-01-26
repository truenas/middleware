import contextlib
import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import (
    user, group, unprivileged_user_client, temporary_update
)
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_method_calls

BASE_SYNTHETIC_DATASTORE_ID = 100000000
DS_USR_VERR_STR = "Directory services users may not be added as members of local groups."
DS_GRP_VERR_STR = "Local users may not be members of directory services groups."

# Alias
pp = pytest.param


@pytest.fixture(scope="module")
def root_user():
    orig_groups = []
    root_id = None  # should be 1
    try:
        root_info = call("user.query", [["username", "=", "root"], ["local", "=", True]], {"get": True})
        root_id = root_info['id']
        orig_groups = root_info['groups']
        yield root_info
    finally:
        # Restore original group list
        call('user.update', root_id, {"groups": orig_groups})


@pytest.fixture(scope="module")
def builtin_admin_group():
    orig_users = []
    group_id = None  # should be 40
    try:
        group_info = call("group.query", [["group", "=", "builtin_administrators"]], {"get": True})
        group_id = group_info['id']
        orig_users = group_info['users']
        yield group_info
    finally:
        # restore original user list
        call('group.update', group_id, {"users": orig_users})


@pytest.fixture(scope="function")
def admin_users():
    builtin_administrators_group_id = call(
        "datastore.query",
        "account.bsdgroups",
        [["group", "=", "builtin_administrators"]],
        {"get": True, "prefix": "bsdgrp_"},
    )["id"]
    with user({
        "username": "adminuser",
        "full_name": "adminuser",
        "group_create": True,
        "password": "canary",
        "groups": [builtin_administrators_group_id],
    }):
        fa_users = call('user.query', [
            ["roles", "rin", "FULL_ADMIN"], ["local", "=", True], ["locked", "=", False]
        ])
        yield fa_users


def test_create_account_audit():
    user_id = None
    payload = {
        "username": "sergey",
        "full_name": "Sergey",
        "group_create": True,
        "password": "password",
    }
    try:
        with expect_audit_method_calls([{
            "method": "user.create",
            "params": [{**payload, "password": "********"}],
            "description": "Create user sergey",
        }]):
            user_id = call("user.create", payload)['id']
    finally:
        if user_id is not None:
            call("user.delete", user_id)


def test_update_account_audit(test_user):
    with temporary_update(test_user, {}, with_audit=True):
        pass


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
    payload = {"name": "group2"}
    try:
        with expect_audit_method_calls([{
            "method": "group.create",
            "params": [payload],
            "description": "Create group group2",
        }]):
            group_id = call("group.create", payload)
    finally:
        if group_id is not None:
            call("group.delete", group_id)


def test_update_group_audit():
    with group({"name": "group2"}) as g:
        with expect_audit_method_calls([{
            "method": "group.update",
            "params": [g["id"], {}],
            "description": "Update group group2",
        }]):
            call("group.update", g["id"], {})


def test_delete_group_audit():
    with group({"name": "group2"}) as g:
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
        with group({
            "name": "local_ds",
            "users": [BASE_SYNTHETIC_DATASTORE_ID + 1]
        }):
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
    with pytest.raises(ValidationErrors, match='Requesting a randomized password while'):
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
    }) as u:
        assert u['password']


def test_update_user_with_random_password(test_user):
    user_id = test_user["id"]
    old_password = test_user["password"]

    try:
        new_entry = call("user.update", user_id, {"random_password": True})
        assert new_entry["password"] != old_password

        with temporary_update(new_entry, {"full_name": "bob2"}) as newer_entry:
            assert not newer_entry["password"]

    finally:
        # Rollback state
        call("user.update", user_id, {"password": old_password})


def test_account_create_invalid_username():
    with pytest.raises(ValidationErrors, match="Valid characters are:"):
        with user({
            "username": "_блин",
            "full_name": "bob",
            "group_create": True,
            "password": "canary"
        }):
            pass


def test_account_update_invalid_username(test_user: dict):
    with pytest.raises(ValidationErrors, match="Valid characters are:"):
        with temporary_update(test_user, {"username": "_блин"}):
            pass


@pytest.mark.parametrize("name", [
    pp("root", id="root is last"),
    pp("adminuser", id="admin_user is last"),
])
def test_account_last_admin(admin_users, name):
    ''' With all FULL_ADMIN users except one 'locked', confirm
        that we cannot lock the last remaining FULL_ADMIN user'''

    admin_users_count = len(admin_users)
    assert admin_users_count >= 2, admin_users

    admin_to_lock = [usr for usr in admin_users if usr['username'] != name]
    assert len(admin_to_lock) == admin_users_count - 1, admin_to_lock

    last_admin = [usr for usr in admin_users if usr['username'] == name][0]
    assert last_admin['username'] == name

    with contextlib.ExitStack() as es:
        # This loop tests the passing case: lock the other admin users
        for fa_user in admin_to_lock:
            es.enter_context(temporary_update(fa_user, {"locked": True}))

        with pytest.raises(ValidationErrors, match='After locking this user'):
            with temporary_update(last_admin, {"locked": True}):
                pass


def test_root_is_full_admin_and_in_builtin_admins(root_user, builtin_admin_group):
    """Confirm the root user account is a member of the 'builtin_administrators' group."""
    assert builtin_admin_group['id'] in root_user['groups']
    assert "FULL_ADMIN" in root_user["roles"], \
        f"root user does not have FULL_ADMIN role. Roles: {root_user['roles']}"


@pytest.mark.parametrize("via_type", [
    pp("user", id="user.update"),
    pp("group", id="group.update")
])
def test_cannot_remove_root_from_builtin_admins(root_user, builtin_admin_group, via_type):
    """Confirm we cannot remove the root user from builtin_administrators
       or change the assigned role."""

    # Configuration for different update methods
    config = {
        "user": {
            "prepare_payload": lambda: [g for g in root_user["groups"] if g != builtin_admin_group["id"]],
            "call_update": lambda payload: call("user.update", root_user["id"], {"groups": payload}),
        },
        "group": {
            "prepare_payload": lambda: [u for u in builtin_admin_group["users"] if u != root_user["id"]],
            "call_update": lambda payload: call("group.update", builtin_admin_group["id"], {"users": payload}),
        }
    }

    # Get the configuration for this test type
    test_config = config[via_type]

    # Prepare the payload that would remove root from builtin_administrators
    payload = test_config["prepare_payload"]()

    # Try to remove root from builtin_administrators (should fail)
    with pytest.raises((ValidationErrors, CallError), match="must remain a member"):
        test_config["call_update"](payload)

    # Verify the root user still has builtin_administrators
    root_user_after = call("user.query", [["username", "=", "root"]], {"get": True})
    assert builtin_admin_group["id"] in root_user_after["groups"], \
        f"root user was incorrectly removed from builtin_administrators via {via_type}.update"

    # And continues to have the FULL_ADMIN role and none other
    assert len(root_user_after["roles"]) == 1
    assert "FULL_ADMIN" in root_user_after["roles"], \
        "root user's FULL_ADMIN role was incorrectly removed"


def test_cannot_add_root_to_other_groups(root_user):
    """Confirm we cannot add the root user to other groups."""

    # Create a test group to try adding root to
    with group({"name": "test_group_for_root"}) as test_grp:
        # Try to add the test group to root's groups
        new_groups = root_user["groups"] + [test_grp["id"]]

        with pytest.raises((ValidationErrors, CallError), match="may only be a member"):
            call("user.update", root_user["id"], {"groups": new_groups})

        # Verify root only has builtin_administrators
        root_user_after = call("user.query", [["username", "=", "root"]], {"get": True})
        assert root_user_after["groups"] == root_user["groups"], \
            "root user's groups were incorrectly modified"


def test_groups_cannot_add_root_to_other_groups(root_user):
    """Confirm we cannot add root to other groups via group management"""

    # Attempt create a test group that includes root
    with pytest.raises(ValidationErrors, match="Cannot add the root user"):
        # use contextmgr for automatic cleanup
        with group({"name": "not_for_root", "users": [root_user['id']]}):
            pass  # should not get here

    # Create a group then attempt add root to the group
    with group({"name": "not_for_root"}) as test_grp:
        with pytest.raises(ValidationErrors, match="Cannot add the root user"):
            call("group.update", test_grp['id'], {"users": [root_user['id']]})


def test_cannot_enable_webshare_for_root_user(root_user):
    with pytest.raises(ValidationErrors, match='not allowed access via webshare'):
        call('user.update', root_user['id'], {"webshare": True})
