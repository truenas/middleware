import contextlib
import errno
import time

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import (
    user, group, unprivileged_user_client, temporary_update
)
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_method_calls

BASE_SYNTHETIC_DATASTORE_ID = 100000000
CONTAINER_ROOT_UID = 2147000001
CONTAINER_ROOT_NAME = "truenas_container_unpriv_root"
NO_LOGIN_SHELL = "/usr/sbin/nologin"
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _vuser(**overrides):
    """Base payload for a non-SMB local user, used to exercise validation paths."""
    payload = {
        "username": "covuser",
        "full_name": "cov user",
        "group_create": True,
        "smb": False,
        "password": "test1234",
    }
    payload.update(overrides)
    return payload


def _a_builtin_user():
    return call("user.query", [["builtin", "=", True], ["username", "!=", "root"]])[0]


# ---------------------------------------------------------------------------
# validate_sudo_commands
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("commands,substring", [
    (["ALL", "/usr/bin/id"], "ALL cannot be used with other commands"),
    (["id"], "Executable must be an absolute path"),
    (["/usr/bin/../bin/id"], "Executable path must be normalized"),
    (["/nonexistent/cov_binary_xyz"], "No paths matching"),
    (["/etc/hostname"], "is executable"),
])
def test_create_user_invalid_sudo_commands(commands, substring):
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covsudo", sudo_commands=commands))

    assert substring in str(ve.value), ve.value


def test_create_user_invalid_sudo_commands_nopasswd():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covsudo", sudo_commands_nopasswd=["id"]))

    assert "Executable must be an absolute path" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# common_validation (username / password / home_mode / full_name / shell)
# ---------------------------------------------------------------------------
def test_create_user_duplicate_username():
    with user(_vuser(username="covdup", home_create=False)):
        with pytest.raises(ValidationErrors) as ve:
            call("user.create", _vuser(username="covdup"))

        assert 'The username "covdup" already exists.' in str(ve.value), ve.value


def test_create_user_password_required():
    payload = {"username": "covnopw", "full_name": "cov", "group_create": True, "smb": False}
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", payload)

    assert "Password is required" in str(ve.value), ve.value


def test_create_user_password_disabled_with_password():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covpwd", password_disabled=True))

    assert 'Leave "Password" blank when "Disable password login" is checked.' in str(ve.value), ve.value


@pytest.mark.parametrize("home_mode,substring", [
    ("077", "Home directory must be readable by User."),
    ("600", "Home directory must be executable by User."),
    ("qqq", "Please provide a valid value for home_mode attribute"),
])
def test_create_user_invalid_home_mode(home_mode, substring):
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covmode", home_mode=home_mode))

    assert substring in str(ve.value), ve.value


def test_create_user_invalid_full_name():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covname", full_name="bad:name"))

    assert "character is not allowed" in str(ve.value), ve.value


def test_create_user_invalid_shell():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covshell", shell="/nonexistent/shell"))

    assert "Please select a valid shell." in str(ve.value), ve.value


def test_create_user_nologin_shell_with_ssh_password():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(
            username="covssh", shell=NO_LOGIN_SHELL, ssh_password_enabled=True,
        ))

    assert "SSH password login requires a login shell." in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# do_update primary group validation
# ---------------------------------------------------------------------------
def test_update_user_group_none(test_user):
    with pytest.raises(ValidationErrors) as ve:
        call("user.update", test_user["id"], {"group": None})

    assert "User must have a primary group" in str(ve.value), ve.value


def test_update_user_group_not_found(test_user):
    with pytest.raises(ValidationErrors) as ve:
        call("user.update", test_user["id"], {"group": BASE_SYNTHETIC_DATASTORE_ID - 10})

    assert "not found" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# builtin / immutable users
# ---------------------------------------------------------------------------
def test_update_immutable_user_home_mode():
    bu = _a_builtin_user()
    with pytest.raises((ValidationErrors, CallError)) as ve:
        call("user.update", bu["id"], {"home_mode": "755"})

    assert "This attribute cannot be changed" in str(ve.value), ve.value


def test_update_immutable_user_username():
    bu = _a_builtin_user()
    with pytest.raises((ValidationErrors, CallError)) as ve:
        call("user.update", bu["id"], {"username": bu["username"] + "_cov"})

    assert "This attribute cannot be changed" in str(ve.value), ve.value


def test_delete_builtin_user():
    bu = _a_builtin_user()
    with pytest.raises(CallError) as ve:
        call("user.delete", bu["id"])

    assert "built-in user" in ve.value.errmsg


# ---------------------------------------------------------------------------
# user.get_user_obj
# ---------------------------------------------------------------------------
def test_get_user_obj_no_arguments():
    with pytest.raises(ValidationErrors) as ve:
        call("user.get_user_obj", {})

    assert 'Either "username" or "uid" must be specified.' in str(ve.value), ve.value


def test_get_user_obj_both_arguments():
    with pytest.raises(ValidationErrors) as ve:
        call("user.get_user_obj", {"username": "root", "uid": 0})

    assert '"username" and "uid" may not be simultaneously specified' in str(ve.value), ve.value


def test_get_user_obj_container_root_by_name():
    obj = call("user.get_user_obj", {"username": CONTAINER_ROOT_NAME})
    assert obj["pw_uid"] == CONTAINER_ROOT_UID


def test_get_user_obj_container_root_by_uid():
    obj = call("user.get_user_obj", {"uid": CONTAINER_ROOT_UID})
    assert obj["pw_name"] == CONTAINER_ROOT_NAME


def test_get_user_obj_nonexistent_username():
    with pytest.raises(Exception) as ve:
        call("user.get_user_obj", {"username": "cov_nonexistent_user_xyz"})

    assert "user with this name does not exist" in str(ve.value)


def test_get_user_obj_nonexistent_uid():
    with pytest.raises(Exception) as ve:
        call("user.get_user_obj", {"uid": 88888})

    assert "user with this id does not exist" in str(ve.value)


def test_get_user_obj_get_groups():
    obj = call("user.get_user_obj", {"username": "root", "get_groups": True})
    assert isinstance(obj["grouplist"], list)


def test_get_user_obj_sid_info_local():
    obj = call("user.get_user_obj", {"username": "root", "sid_info": True})
    assert obj["source"] == "LOCAL"
    assert obj["local"] is True


# ---------------------------------------------------------------------------
# setup_local_administrator
# ---------------------------------------------------------------------------
def test_has_local_administrator_set_up():
    assert call("user.has_local_administrator_set_up") is True


def test_setup_local_administrator_already_set_up():
    with pytest.raises(CallError) as ve:
        call("user.setup_local_administrator", "truenas_admin", "coverage_password")

    assert "already set up" in ve.value.errmsg
    assert ve.value.errno == errno.EEXIST


# ---------------------------------------------------------------------------
# userns_idmap
# ---------------------------------------------------------------------------
def test_create_user_userns_idmap_direct():
    with user(_vuser(username="covidmap", userns_idmap="DIRECT")) as u:
        assert u["userns_idmap"] == "DIRECT"
        assert call("user.get_instance", u["id"])["userns_idmap"] == "DIRECT"


def test_user_userns_idmap_conflict():
    with user(_vuser(username="covidmapa", userns_idmap=500000)):
        with pytest.raises(ValidationErrors) as ve:
            with user(_vuser(username="covidmapb", userns_idmap=500000)):
                pass

        assert "already maps to container UID" in str(ve.value), ve.value


def test_update_builtin_user_userns_idmap_forbidden():
    bu = _a_builtin_user()
    with pytest.raises((ValidationErrors, CallError)) as ve:
        call("user.update", bu["id"], {"userns_idmap": "DIRECT"})

    assert "builtin accounts" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# user.set_password
# ---------------------------------------------------------------------------
def test_set_password_by_full_admin():
    with user(_vuser(username="covsetpw")):
        call("user.set_password", {"username": "covsetpw", "new_password": "NewCovPass1!"})


def test_set_password_nonexistent_user():
    with pytest.raises(ValidationErrors) as ve:
        call("user.set_password", {"username": "cov_nonexistent_setpw", "new_password": "NewCovPass1!"})

    assert "user does not exist" in str(ve.value), ve.value


def test_set_password_locked_user():
    with user(_vuser(username="covlocked", locked=True)):
        with pytest.raises(ValidationErrors) as ve:
            call("user.set_password", {"username": "covlocked", "new_password": "NewCovPass1!"})

        assert "user account is locked" in str(ve.value), ve.value


def test_set_password_disabled_user():
    payload = {"username": "covpwdis", "full_name": "cov", "group_create": True,
               "smb": False, "password_disabled": True}
    with user(payload):
        with pytest.raises(ValidationErrors) as ve:
            call("user.set_password", {"username": "covpwdis", "new_password": "NewCovPass1!"})

        assert "password authentication disabled" in str(ve.value), ve.value


def test_set_password_other_user_forbidden():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        with pytest.raises(CallError) as ve:
            c.call("user.set_password", {"username": "root", "new_password": "NewCovPass1!"})

        assert ve.value.errno == errno.EPERM


def test_set_password_self_requires_old_password():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        with pytest.raises(ValidationErrors) as ve:
            c.call("user.set_password", {"username": c.username, "new_password": "NewCovPass1!"})

        assert "FULL_ADMIN role is required" in str(ve.value), ve.value


def test_set_password_self_wrong_old_password():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        with pytest.raises(ValidationErrors) as ve:
            c.call("user.set_password", {
                "username": c.username,
                "old_password": "wrongpassword",
                "new_password": "NewCovPass1!",
            })

        assert "failed to validate password" in str(ve.value), ve.value


def test_set_password_self_success():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        c.call("user.set_password", {
            "username": c.username,
            "old_password": "test1234",
            "new_password": "NewCovPass1!",
        })


# ---------------------------------------------------------------------------
# validate_sudo_commands - success paths
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("field", ["sudo_commands", "sudo_commands_nopasswd"])
@pytest.mark.parametrize("commands", [["ALL"], ["/usr/bin/id"]])
def test_create_user_valid_sudo_commands(field, commands):
    with user(_vuser(username="covsudook", **{field: commands})) as u:
        assert call("user.get_instance", u["id"])[field] == commands


# ---------------------------------------------------------------------------
# filters_include_ds_accounts branches (exercised via user.query)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("filters", [
    [["OR", [["local", "=", True], ["uid", "=", 0]]]],  # connective: len(f) < 3
    [["local", "!=", False]],                            # '!=' False -> local only
    [["builtin", "in", [True, False]]],                  # operator other than = / !=
])
def test_user_query_local_filter_variants(filters):
    # We only care that the filter is accepted and the code path runs.
    result = call("user.query", filters)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# do_create - primary group selection branches
# ---------------------------------------------------------------------------
def test_create_user_without_group_or_group_create():
    payload = {"username": "covnogrp", "full_name": "cov", "smb": False, "password": "test1234"}
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", payload)

    assert "Enter either a group name or create a new group" in str(ve.value), ve.value


def test_create_user_group_create_reuses_existing_named_group():
    # When group_create is requested but a local group already shares the
    # username, do_create reuses it instead of creating a duplicate.
    with group({"name": "covreuse", "smb": False}) as g:
        with user({
            "username": "covreuse",
            "full_name": "cov",
            "group_create": True,
            "smb": False,
            "password": "test1234",
        }) as u:
            assert call("user.get_instance", u["id"])["group"]["id"] == g["id"]


def test_create_user_group_not_found():
    payload = {
        "username": "covbadgrp",
        "full_name": "cov",
        "group": BASE_SYNTHETIC_DATASTORE_ID - 20,
        "smb": False,
        "password": "test1234",
    }
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", payload)

    assert "not found" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# do_update - successful mutations
# ---------------------------------------------------------------------------
def test_update_user_change_primary_group():
    with group({"name": "covnewpri", "smb": False}) as g:
        with user(_vuser(username="covchggrp")) as u:
            updated = call("user.update", u["id"], {"group": g["id"]})
            assert updated["group"]["id"] == g["id"]


def test_update_user_password_history_maintained():
    # Updating the password twice exercises the password-history bookkeeping.
    with user(_vuser(username="covpwhist")) as u:
        call("user.update", u["id"], {"password": "FirstPass1!"})
        call("user.update", u["id"], {"password": "SecondPass2!"})
        entry = call(
            "user.query", [["id", "=", u["id"]]],
            {"get": True, "extra": {"additional_information": []}},
        )
        assert entry["last_password_change"] is not None


def test_update_user_enable_smb_requires_password():
    # Converting a non-SMB user to SMB without a password is rejected (917).
    with user(_vuser(username="covtosmb")) as u:
        with pytest.raises(ValidationErrors) as ve:
            call("user.update", u["id"], {"smb": True})

        assert "Password must be reset in order to enable SMB authentication" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# builtin group membership restriction
# ---------------------------------------------------------------------------
def test_create_user_cannot_join_restricted_builtin_group():
    ALLOWED = {14, 445, 544, 545, 568, 951, 952}
    restricted = next(
        g for g in call("group.query", [["builtin", "=", True]])
        if g["gid"] not in ALLOWED
    )
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covbgrp", groups=[restricted["id"]]))

    assert "membership of this builtin group may not be altered" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# get_next_uid gap-filling
# ---------------------------------------------------------------------------
def test_get_next_uid_is_unique():
    next_uid = call("user.get_next_uid")
    with user(_vuser(username="covnextuid", uid=next_uid)):
        assert call("user.get_next_uid") != next_uid


# ---------------------------------------------------------------------------
# SMB user lifecycle (passdb create / update / delete)
# ---------------------------------------------------------------------------
def test_smb_user_lifecycle():
    with user({
        "username": "covsmbuser",
        "full_name": "cov smb",
        "group_create": True,
        "smb": True,
        "password": "SmbPass123!",
    }) as u:
        # user is present in the SMB passdb
        assert any(e["username"] == "covsmbuser" for e in call("smb.passdb_list"))

        # update an SMB user (exercises smb.update_passdb_user on update)
        call("user.update", u["id"], {"full_name": "cov smb renamed"})

        # reset password on an SMB user (exercises smb passdb on set_password)
        call("user.set_password", {"username": "covsmbuser", "new_password": "SmbPass456!"})


# ---------------------------------------------------------------------------
# SMB username case-insensitive conflict
# ---------------------------------------------------------------------------
def test_smb_username_case_insensitive_conflict():
    with user({
        "username": "CovSmbUser",
        "full_name": "cov",
        "group_create": True,
        "smb": True,
        "password": "SmbPass123!",
    }):
        with pytest.raises(ValidationErrors) as ve:
            call("user.create", {
                "username": "covsmbuser",
                "full_name": "cov",
                "group_create": True,
                "smb": True,
                "password": "SmbPass123!",
            })

        assert "conflicts with existing SMB user" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# userns_idmap not allowed on privileged accounts
# ---------------------------------------------------------------------------
def test_create_user_userns_idmap_privileged_group():
    with group({"name": "covprivug", "smb": False}) as g:
        with privilege({
            "name": "Cov Priv UG",
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }):
            with pytest.raises(ValidationErrors) as ve:
                call("user.create", _vuser(
                    username="covprivuser", group_create=True,
                    groups=[g["id"]], userns_idmap="DIRECT",
                ))

            assert "may not be configured for privileged accounts" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# password security policy (complexity / length / history)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _password_security(**settings):
    # Password policy fields are gated to TrueNAS Enterprise, so we present as
    # Enterprise (with FIPS available) for the duration of the test.
    from middlewared.test.integration.assets.product import product_type, set_fips_available

    fields = ["password_complexity_ruleset", "min_password_length", "password_history_length"]
    with product_type("ENTERPRISE"), set_fips_available(True):
        old = call("system.security.config")
        restore = {k: old[k] for k in fields}
        call("system.security.update", settings, job=True)
        try:
            yield
        finally:
            call("system.security.update", restore, job=True)


def test_create_user_password_too_short():
    with _password_security(min_password_length=20):
        with pytest.raises(ValidationErrors) as ve:
            call("user.create", _vuser(username="covshortpw", password="short"))

        assert "password is too short" in str(ve.value), ve.value


def test_set_password_history_reuse_rejected():
    with _password_security(password_history_length=3):
        with user(_vuser(username="covhistpw", password="HistPass1!")) as u:
            # change to a new password, then attempt to reuse the previous one
            call("user.set_password", {"username": "covhistpw", "new_password": "HistPass2!"})
            with pytest.raises(ValidationErrors) as ve:
                call("user.set_password", {"username": "covhistpw", "new_password": "HistPass1!"})

            assert "does not match any of the last" in str(ve.value), ve.value
            # cleanup relies on user() teardown; ensure entry still exists
            assert call("user.get_instance", u["id"])["username"] == "covhistpw"


def test_set_password_history_only_checks_configured_length():
    # Reuse is forbidden only for the last `password_history_length` passwords,
    # even when more hashes are stored. The comparison loop walks the stored
    # hashes newest-first and `break`s once it has examined that many, so an
    # *older* stored password remains reusable. With a history length of 1:
    #   - reusing the current (most-recent) password is rejected, but
    #   - the older password is accepted, precisely because the loop breaks
    #     before comparing against its hash.
    with _password_security(password_history_length=1):
        with user(_vuser(username="covhistbrk", password="HistP0!")):
            call("user.set_password", {"username": "covhistbrk", "new_password": "HistP1!"})

            with pytest.raises(ValidationErrors) as ve:
                call("user.set_password", {"username": "covhistbrk", "new_password": "HistP1!"})
            assert "does not match any of the last" in str(ve.value), ve.value

            # older-than-configured-length password is allowed thanks to the break
            call("user.set_password", {"username": "covhistbrk", "new_password": "HistP0!"})


def test_password_history_capped_at_max():
    # Stored password history is capped at MAX_PASSWORD_HISTORY (10); changing the
    # password more than that many times exercises the trim (`pop(0)`) loop.
    with user(_vuser(username="covpwcap")) as u:
        for i in range(12):
            call("user.update", u["id"], {"password": f"CovCapPass{i}!"})

        stored = call(
            "datastore.query", "account.bsdusers",
            [["id", "=", u["id"]]], {"get": True, "prefix": "bsdusr_"},
        )["password_history"]
        assert 0 < len(stored.split()) <= 10


def test_user_password_change_required_soft_limit():
    from middlewared.test.integration.assets.product import product_type, set_fips_available

    with product_type("ENTERPRISE"), set_fips_available(True):
        call("system.security.update", {"max_password_age": 30}, job=True)
        try:
            with user(_vuser(username="covpwage")) as u:
                backdated = int(time.time()) - 86400 * 40
                call("datastore.update", "account.bsdusers", u["id"],
                     {"bsdusr_last_password_change": backdated})
                assert call("user.get_instance", u["id"])["password_change_required"] is True
        finally:
            call("system.security.update", {"max_password_age": None}, job=True)


# ---------------------------------------------------------------------------
# SMB user rename / disable (passdb bookkeeping on update)
# ---------------------------------------------------------------------------
def test_smb_user_rename_and_disable():
    with user({
        "username": "covsmbtog",
        "full_name": "cov",
        "group_create": True,
        "smb": True,
        "password": "SmbPass123!",
    }) as u:
        # rename: old passdb entry removed, new one added
        call("user.update", u["id"], {"username": "covsmbtog2"})
        assert any(e["username"] == "covsmbtog2" for e in call("smb.passdb_list"))

        # disable SMB: passdb entry removed
        call("user.update", u["id"], {"smb": False})
        assert not any(e["username"] == "covsmbtog2" for e in call("smb.passdb_list"))


# ---------------------------------------------------------------------------
# deleting a user reassigns the SMB guest account back to nobody
# ---------------------------------------------------------------------------
def test_delete_user_reassigns_cifs_guest():
    cifs = call("datastore.query", "services.cifs", [], {"get": True, "prefix": "cifs_srv_"})
    original_guest = cifs["guest"]
    with user({
        "username": "covguest",
        "full_name": "cov",
        "group_create": True,
        "smb": True,
        "password": "SmbPass123!",
    }) as u:
        call("datastore.update", "services.cifs", cifs["id"],
             {"guest": "covguest"}, {"prefix": "cifs_srv_"})
        try:
            call("user.delete", u["id"])
            after = call("datastore.query", "services.cifs", [], {"get": True, "prefix": "cifs_srv_"})
            assert after["guest"] == "nobody"
        finally:
            call("datastore.update", "services.cifs", cifs["id"],
                 {"guest": original_guest}, {"prefix": "cifs_srv_"})


# ---------------------------------------------------------------------------
# password age of an account whose last change is in the future is None
# ---------------------------------------------------------------------------
def test_user_password_age_future_is_none():
    with user(_vuser(username="covfuture")) as u:
        future = int(time.time()) + 86400 * 365
        call("datastore.update", "account.bsdusers", u["id"],
             {"bsdusr_last_password_change": future})
        entry = call("user.get_instance", u["id"])
        assert entry["password_age"] is None


# ---------------------------------------------------------------------------
# local API keys surface in user.query (user_extend_context)
# ---------------------------------------------------------------------------
def test_user_local_api_key_listed():
    # API keys can only be issued to privileged users, so add the account to
    # builtin_administrators before creating the key.
    ba_id = call("group.query", [["group", "=", "builtin_administrators"]], {"get": True})["id"]
    with user(_vuser(username="covapikey", groups=[ba_id])) as u:
        with api_key(username="covapikey") as _key:
            entry = call("user.get_instance", u["id"])
            assert len(entry["api_keys"]) == 1


# ---------------------------------------------------------------------------
# disabling password login (privilege.before_user_password_disable)
# ---------------------------------------------------------------------------
def test_update_user_password_disabled_allowed():
    # Disabling password for a non-administrator succeeds: the privilege guard
    # is consulted but does not object (root remains a password-enabled admin).
    with user(_vuser(username="covpwdisok")) as u:
        updated = call("user.update", u["id"], {"password_disabled": True})
        assert updated["password_disabled"] is True


# ---------------------------------------------------------------------------
# SMB <-> non-SMB conversion on update
# ---------------------------------------------------------------------------
def test_update_enable_smb_with_password():
    with user(_vuser(username="covensmb")) as u:
        call("user.update", u["id"], {"smb": True, "password": "SmbPass123!"})
        assert any(e["username"] == "covensmb" for e in call("smb.passdb_list"))


def test_create_smb_user_password_disabled_rejected():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", {
            "username": "covsmbpwd",
            "full_name": "cov",
            "group_create": True,
            "smb": True,
            "password_disabled": True,
        })

    assert "Password authentication may not be disabled for SMB users." in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# auxiliary group count / duplicate uid
# ---------------------------------------------------------------------------
def test_create_user_too_many_groups():
    with pytest.raises(ValidationErrors) as ve:
        call("user.create", _vuser(username="covmanygrp", groups=list(range(1_000_000, 1_000_065))))

    assert "cannot belong to more than 64 auxiliary groups" in str(ve.value), ve.value


def test_create_user_duplicate_uid():
    with user(_vuser(username="covuida", uid=59123)):
        with pytest.raises(ValidationErrors) as ve:
            call("user.create", _vuser(username="covuidb", uid=59123))

        assert "Uid 59123 is already used" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# webshare group membership add/remove (handle_webshare)
# ---------------------------------------------------------------------------
def test_webshare_membership_add_and_remove():
    webshare_gid = call("group.query", [["name", "=", "truenas_webshare"]], {"get": True})["id"]
    with user(_vuser(username="covws", webshare=True)) as u:
        assert webshare_gid in call("user.get_instance", u["id"])["groups"]

        call("user.update", u["id"], {"webshare": False})
        assert webshare_gid not in call("user.get_instance", u["id"])["groups"]


# ---------------------------------------------------------------------------
# webui attribute is removed when the user is deleted
# ---------------------------------------------------------------------------
def test_delete_user_removes_webui_attribute():
    with user(_vuser(username="covwebui")) as u:
        uid = call("user.get_instance", u["id"])["uid"]
        call("datastore.insert", "account.bsdusers_webui_attribute",
             {"uid": uid, "attributes": {"foo": "bar"}})
        assert call("datastore.query", "account.bsdusers_webui_attribute", [["uid", "=", uid]])

        call("user.delete", u["id"])
        assert call("datastore.query", "account.bsdusers_webui_attribute", [["uid", "=", uid]]) == []


