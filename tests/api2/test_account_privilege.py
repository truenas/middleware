import errno
import os
import sys
import types

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import group, privilege, root_with_password_disabled
from middlewared.test.integration.utils import call, mock
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())


def test_change_local_administrator_groups_to_invalid():
    operator = call("group.query", [["group", "=", "operator"]], {"get": True})

    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", 1, {"local_groups": [operator["id"]]})

    assert ve.value.errors[0].attribute == "privilege_update.local_groups"


def test_change_local_administrator_roles():
    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", 1, {"roles": ['READONLY_ADMIN']})

    assert ve.value.errors[0].attribute == "privilege_update.roles"


def test_delete_local_administrator():
    with pytest.raises(CallError) as ve:
        call("privilege.delete", 1)

    assert ve.value.errno == errno.EPERM


def test_invalid_local_group():
    with pytest.raises(ValidationErrors) as ve:
        call("privilege.create", {
            "name": "Test",
            "local_groups": [1024],  # invalid local group ID
            "ds_groups": [],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        })

    assert ve.value.errors[0].attribute == "privilege_create.local_groups.0"


def test_delete_local_administrator_group():
    with group({
        "name": "test_local_admins",
    }) as g:
        local_groups = [lg["gid"] for lg in call("privilege.get_instance", 1)["local_groups"]]
        call("privilege.update", 1, {"local_groups": local_groups + [g["gid"]]})

        with pytest.raises(CallError) as ve:
            call("group.delete", g["id"])

        assert ve.value.errmsg.startswith("This group is used by privilege")

        call("privilege.update", 1, {"local_groups": local_groups})


@pytest.fixture(scope="module")
def privilege_with_orphan_local_group():
    with group({
        "name": "test_orphan",
        "smb": False,
    }) as g:
        gid = g["gid"]
        privilege = call("privilege.create", {
            "name": "Test orphan",
            "local_groups": [gid],
            "ds_groups": [],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        })
        call("datastore.delete", "account.bsdgroups", g["id"])
        call("etc.generate", "user")
        call("idmap.gencache.flush")

    yield types.SimpleNamespace(gid=gid, privilege=privilege)

    call("privilege.delete", privilege["id"])


def test_create_group_with_orphan_privilege_gid(privilege_with_orphan_local_group):
    with pytest.raises(ValidationErrors) as ve:
        with group({
            "name": "test_orphan_duplicate",
            "gid": privilege_with_orphan_local_group.gid,
        }):
            pass

    assert ve.value.errors[0].attribute == "group_create.gid"
    assert ve.value.errors[0].errmsg.startswith("A privilege 'Test orphan' already uses this group ID.")


def test_group_next_gid():
    next_gid = call("group.get_next_gid")
    with mock("privilege.used_local_gids", f"""
        async def mock(self):
            result = await self.used_local_gids()
            result[{next_gid}] = None
            return result
    """):
        assert call("group.get_next_gid") == next_gid + 1


def test_remove_only_local_administrator_password_enabled_user():
    root = call("user.query", [["username", "=", "root"]], {"get": True})
    with pytest.raises(ValidationErrors) as ve:
        call("user.update", root["id"], {"password_disabled": True})

    assert ve.value.errors[0].attribute == "user_update.password_disabled"
    assert ve.value.errors[0].errmsg == (
        "After disabling password for this user no password-enabled local user will have built-in privilege "
        "'Local Administrator'."
    )


def test_password_disabled_root_is_a_local_administrator():
    with root_with_password_disabled():
        local_administrators = call("privilege.local_administrators")

        assert len(local_administrators) == 1
        assert local_administrators[0]["username"] == "root"


def test_create_privilege_audit():
    privilege = None
    try:
        with expect_audit_method_calls([{
            "method": "privilege.create",
            "params": [
                {
                    "name": "Test",
                    "web_shell": False,
                }
            ],
            "description": "Create privilege Test",
        }]):
            privilege = call("privilege.create", {
                "name": "Test",
                "web_shell": False,
            })
    finally:
        if privilege is not None:
            call("privilege.delete", privilege["id"])


def test_update_privilege_audit():
    with privilege({
        "name": "Test",
        "web_shell": False,
    }) as p:
        with expect_audit_method_calls([{
            "method": "privilege.update",
            "params": [p["id"], {}],
            "description": "Update privilege Test",
        }]):
            call("privilege.update", p["id"], {})


def test_delete_privilege_audit():
    with privilege({
        "name": "Test",
        "web_shell": False,
    }) as p:
        with expect_audit_method_calls([{
            "method": "privilege.delete",
            "params": [p["id"]],
            "description": "Delete privilege Test",
        }]):
            call("privilege.delete", p["id"])
