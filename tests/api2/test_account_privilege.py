import contextlib
import errno
import os
import sys
import types

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import group, privilege, root_with_password_disabled, user
from middlewared.test.integration.utils import call, client, mock
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())

# A well-formed SID that no directory service on the test system can map.
UNMAPPED_SID = "S-1-5-21-1234567890-1234567890-1234567890-1234"
# A GID that is not assigned to any local group.
UNUSED_GID = 59999


@contextlib.contextmanager
def raw_privilege(data):
    """Insert a privilege row directly into the datastore.

    `privilege.create` rejects group ids that cannot be resolved, so this is the
    only way to obtain a privilege whose `ds_groups` are unmapped (which is what
    happens when a directory service is unjoined after privileges were granted).
    """
    id_ = call("datastore.insert", "account.privilege", {
        "builtin_name": None,
        "name": "Test raw",
        "local_groups": [],
        "ds_groups": [],
        "roles": [],
        "web_shell": False,
        **data,
    })
    try:
        yield id_
    finally:
        call("datastore.delete", "account.privilege", id_)


def test_change_local_administrator_groups_to_invalid():
    operator = call("group.query", [["group", "=", "operator"]], {"get": True})

    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", 1, {"local_groups": [operator["id"]]})

    assert ve.value.errors[0].attribute == "privilege_update.local_groups"
    assert ve.value.errors[0].errmsg == (
        "The group builtin_administrators must be among grantees of the \"Local Administrator\" privilege."
    )


def test_change_local_administrator_roles():
    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", 1, {"roles": ['READONLY_ADMIN']})

    assert ve.value.errors[0].attribute == "privilege_update.roles"
    assert ve.value.errors[0].errmsg == "This field is read-only for built-in privileges"


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
        assert call("group.get_next_gid") != next_gid


def test_remove_only_local_administrator_password_enabled_user(root_is_only_local_administrator):
    root = call("user.query", [["username", "=", "root"]], {"get": True})
    with pytest.raises(ValidationErrors) as ve:
        call("user.update", root["id"], {"password_disabled": True})

    assert ve.value.errors[0].attribute == "user_update.password_disabled"
    assert ve.value.errors[0].errmsg == (
        "After disabling password for this user no password-enabled local user will have built-in privilege "
        "'Local Administrator'."
    )


def test_password_disabled_root_is_a_local_administrator(root_is_only_local_administrator):
    with root_with_password_disabled():
        local_administrators = call("privilege.local_administrators")

        assert len(local_administrators) == 1
        assert local_administrators[0]["username"] == "root"


def test_root_without_a_password_is_not_a_local_administrator(root_is_only_local_administrator):
    with root_with_password_disabled() as t:
        # the root fallback only applies while root still has a usable password hash
        t.client.call("datastore.update", "account.bsdusers", t.root_id, {"bsdusr_unixhash": "*"})

        assert call("privilege.local_administrators") == []


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


# ---------------------------------------------------------------------------
# privilege validation
# ---------------------------------------------------------------------------
def test_create_privilege_invalid_role():
    with pytest.raises(ValidationErrors) as ve:
        call("privilege.create", {
            "name": "Test invalid role",
            "roles": ["THIS_ROLE_DOES_NOT_EXIST"],
            "web_shell": False,
        })

    assert ve.value.errors[0].attribute == "privilege_create.roles.0"
    assert ve.value.errors[0].errmsg == "Invalid role"


def test_create_privilege_local_group_with_userns_idmap():
    with group({"name": "test_privilege_userns", "smb": False, "userns_idmap": "DIRECT"}) as g:
        with pytest.raises(ValidationErrors) as ve:
            call("privilege.create", {
                "name": "Test userns idmap",
                "local_groups": [g["gid"]],
                "roles": ["READONLY_ADMIN"],
                "web_shell": False,
            })

        assert ve.value.errors[0].errmsg == (
            "Privileges may not be granted to groups that have a user namespace idmap configured."
        )


@pytest.mark.parametrize("ds_group", [
    pytest.param(UNUSED_GID, id="gid"),
    pytest.param(UNMAPPED_SID, id="sid"),
])
def test_create_privilege_nonexistent_ds_group(ds_group):
    with pytest.raises(ValidationErrors) as ve:
        call("privilege.create", {
            "name": "Test nonexistent ds group",
            "ds_groups": [ds_group],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        })

    assert ve.value.errors[0].attribute == "privilege_create.ds_groups.0"
    assert ve.value.errors[0].errmsg.startswith(f"{ds_group}: directory service group does not exist.")


def test_update_privilege_preserves_unmapped_ds_groups():
    """`privilege.update` converts the extended `ds_groups` back to gid / sid values.

    The privilege is left with unmapped groups, so the update is rejected, but only
    after both an unmapped GID and an unmapped SID have been converted back.
    """
    with raw_privilege({"name": "Test unmapped ds groups", "ds_groups": [UNUSED_GID, UNMAPPED_SID]}) as id_:
        with pytest.raises(ValidationErrors) as ve:
            call("privilege.update", id_, {"web_shell": True})

        assert [(e.attribute, e.errmsg) for e in ve.value.errors] == [
            (
                "privilege_update.ds_groups.0",
                f"{UNUSED_GID}: directory service group does not exist. If the directory service "
                "state is healthy, then this error may be addressed by removing this entry from "
                "the privilege.",
            ),
            (
                "privilege_update.ds_groups.1",
                f"{UNMAPPED_SID}: directory service group does not exist. If the directory service "
                "state is healthy, then this error may be addressed by removing this entry from "
                "the privilege.",
            ),
        ]


def test_update_readonly_administrator_web_shell():
    readonly = call("privilege.query", [["builtin_name", "=", "READONLY_ADMINISTRATOR"]], {"get": True})

    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", readonly["id"], {"web_shell": True})

    assert ve.value.errors[0].attribute == "privilege_update.web_shell"
    assert ve.value.errors[0].errmsg == (
        "Web shell access may not be enabled for the built-in group for read-only administrators."
    )


@pytest.mark.parametrize("builtin_name", ["READONLY_ADMINISTRATOR", "SHARING_ADMINISTRATOR"])
def test_update_builtin_privilege_without_web_shell(builtin_name):
    p = call("privilege.query", [["builtin_name", "=", builtin_name]], {"get": True})

    assert call("privilege.update", p["id"], {"web_shell": False})["web_shell"] is False


def test_update_local_administrator_without_password_enabled_user(root_is_only_local_administrator):
    with root_with_password_disabled():
        local_groups = [lg["gid"] for lg in call("privilege.get_instance", 1)["local_groups"]]

        with pytest.raises(ValidationErrors) as ve:
            call("privilege.update", 1, {"local_groups": local_groups})

        assert ve.value.errors[0].attribute == "privilege_update.local_groups"
        assert ve.value.errors[0].errmsg == (
            "None of the members of these groups has password login enabled. At least one grantee of the "
            "\"Local Administrator\" privilege must have password login enabled."
        )


# ---------------------------------------------------------------------------
# directory service group resolution (`privilege.query` extend)
#
# The paths where a `ds_groups` entry resolves to an actual (non-local) group
# require a joined directory service and are covered by tests/directory_services.
# What is exercised here is everything a stand-alone server can reach: entries
# that resolve to nothing, and entries that resolve to a local account.
# ---------------------------------------------------------------------------
def test_query_privilege_unmapped_ds_group_gid():
    with raw_privilege({"name": "Test unmapped gid", "ds_groups": [UNUSED_GID]}) as id_:
        assert call("privilege.get_instance", id_)["ds_groups"] == [
            {"gid": UNUSED_GID, "sid": None, "group": None},
        ]


def test_query_privilege_unmapped_ds_group_sid():
    with raw_privilege({"name": "Test unmapped sid", "ds_groups": [UNMAPPED_SID]}) as id_:
        assert call("privilege.get_instance", id_)["ds_groups"] == [
            {"gid": None, "sid": UNMAPPED_SID, "group": None},
        ]


@pytest.mark.parametrize("by", ["gid", "sid"])
def test_query_privilege_ds_group_that_is_a_local_group(by):
    """Local groups are never reported as directory service groups."""
    builtin_administrators = call("group.query", [["group", "=", "builtin_administrators"]], {"get": True})
    assert builtin_administrators["sid"] is not None

    with raw_privilege({"name": "Test local ds group", "ds_groups": [builtin_administrators[by]]}) as id_:
        assert call("privilege.get_instance", id_)["ds_groups"] == []


def test_query_privilege_ds_group_sid_of_a_user():
    """A SID that resolves to a user is not a group, so it stays unmapped."""
    with user({
        "username": "test_priv_sid",
        "full_name": "test_priv_sid",
        "group_create": True,
        "smb": True,
        "password": "test1234",
    }) as u:
        sid = call("user.get_instance", u["id"])["sid"]
        assert sid is not None

        with raw_privilege({"name": "Test user sid", "ds_groups": [sid]}) as id_:
            assert call("privilege.get_instance", id_)["ds_groups"] == [
                {"gid": None, "sid": sid, "group": None},
            ]


def test_query_privilege_ds_groups_sid_conversion_failure():
    """An unhealthy domain must not break `privilege.query`."""
    with mock("idmap.convert_sids", """
        async def mock(self, *args):
            raise Exception("winbind is unavailable")
    """):
        with raw_privilege({"name": "Test sid failure", "ds_groups": [UNMAPPED_SID]}) as id_:
            assert call("privilege.get_instance", id_)["ds_groups"] == []


# ---------------------------------------------------------------------------
# privilege.privileges_for_groups
# ---------------------------------------------------------------------------
def test_privileges_for_groups():
    local_administrators_gid = call("privilege.get_instance", 1)["local_groups"][0]["gid"]

    privileges = call("privilege.privileges_for_groups", "local_groups", [local_administrators_gid])
    assert [p["builtin_name"] for p in privileges] == ["LOCAL_ADMINISTRATOR"]

    # the same group is not granted anything as a directory service group
    assert call("privilege.privileges_for_groups", "ds_groups", [local_administrators_gid]) == []


def test_privileges_for_groups_unixid_conversion_failure():
    with mock("idmap.convert_unixids", """
        async def mock(self, *args):
            raise Exception("winbind is unavailable")
    """):
        assert call("privilege.privileges_for_groups", "ds_groups", [544]) == []


# ---------------------------------------------------------------------------
# privilege.become_readonly
# ---------------------------------------------------------------------------
def test_become_readonly():
    with client() as c:
        assert "FULL_ADMIN" in c.call("auth.me")["privilege"]["roles"]

        c.call("privilege.become_readonly")

        composed = c.call("auth.me")["privilege"]
        assert "FULL_ADMIN" not in composed["roles"]
        assert "READONLY_ADMIN" in composed["roles"]
        assert composed["web_shell"] is False

        with pytest.raises(CallError) as ve:
            c.call("group.create", {"name": "test_become_readonly"})

        assert ve.value.errno == errno.EACCES


# ---------------------------------------------------------------------------
# group.has_password_enabled_user
# ---------------------------------------------------------------------------
def test_has_password_enabled_user_ignores_ineligible_members():
    with group({"name": "test_pw_enabled_none", "smb": False}) as g:
        payload = {
            "full_name": "test_pw_enabled",
            "group_create": True,
            "smb": False,
            "groups": [g["id"]],
        }
        with user({**payload, "username": "test_pw_locked", "password": "test1234", "locked": True}):
            with user({**payload, "username": "test_pw_disabled", "password_disabled": True}):
                with user({**payload, "username": "test_pw_nohash", "password": "test1234"}) as u:
                    # an account with no valid unix hash cannot authenticate either
                    call("datastore.update", "account.bsdusers", u["id"], {"bsdusr_unixhash": "*"})

                    assert call("group.has_password_enabled_user", [g["gid"]]) is False


def test_has_password_enabled_user_deduplicates_members():
    with group({"name": "test_pw_enabled_a", "smb": False}) as g1:
        with group({"name": "test_pw_enabled_b", "smb": False}) as g2:
            with user({
                "username": "test_pw_member",
                "full_name": "test_pw_member",
                "group_create": True,
                "smb": False,
                "password": "test1234",
                "groups": [g1["id"], g2["id"]],
            }) as u:
                gids = [g1["gid"], g2["gid"]]
                # the user is a member of both groups but must only be reported once
                enabled = call("group.get_password_enabled_users", gids, [])
                assert [e["username"] for e in enabled] == ["test_pw_member"]
                assert call("group.has_password_enabled_user", gids) is True
                assert call("group.has_password_enabled_user", gids, [u["id"]]) is False
