import pytest

from middlewared.service_exception import CallError, InstanceNotFound, ValidationErrors
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call

BASE_SYNTHETIC_DATASTORE_ID = 100000000


def test_delete_group_delete_users():
    with group({
        "name": "group1",
    }) as g:
        with user({
            "username": "user1",
            "full_name": "user1",
            "group": g["id"],
            "password": "test1234",
        }) as u1:
            with user({
                "username": "user2",
                "full_name": "user2",
                "group": g["id"],
                "password": "test1234",
            }) as u2:
                with user({
                    "username": "user3",
                    "full_name": "user3",
                    "group_create": True,
                    "groups": [g["id"]],
                    "password": "test1234",
                }) as u3:
                    call("group.delete", g["id"], {"delete_users": True})

                    with pytest.raises(InstanceNotFound):
                        call("user.get_instance", u1["id"])
                    with pytest.raises(InstanceNotFound):
                        call("user.get_instance", u2["id"])
                    call("user.get_instance", u3["id"])


# ---------------------------------------------------------------------------
# group.__common_validation
# ---------------------------------------------------------------------------
def test_create_group_duplicate_name():
    with group({"name": "covdupgrp"}):
        with pytest.raises(ValidationErrors) as ve:
            call("group.create", {"name": "covdupgrp"})

        assert 'A Group with the name "covdupgrp" already exists.' in str(ve.value), ve.value


def test_create_group_nonexistent_user():
    with pytest.raises(ValidationErrors) as ve:
        call("group.create", {"name": "covbadusers", "users": [BASE_SYNTHETIC_DATASTORE_ID - 5]})

    assert "do not exist" in str(ve.value), ve.value


@pytest.mark.parametrize("field", ["sudo_commands", "sudo_commands_nopasswd"])
def test_create_group_invalid_sudo_commands(field):
    with pytest.raises(ValidationErrors) as ve:
        call("group.create", {"name": "covgsudo", field: ["id"]})

    assert "Executable must be an absolute path" in str(ve.value), ve.value


def test_group_update_remove_primary_user():
    with group({"name": "covprimarygrp"}) as g:
        with user({
            "username": "covprimaryuser",
            "full_name": "cov",
            "group": g["id"],
            "smb": False,
            "password": "test1234",
        }):
            with pytest.raises(ValidationErrors) as ve:
                call("group.update", g["id"], {"users": []})

            assert "primary for the following users" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# builtin / immutable groups
# ---------------------------------------------------------------------------
def test_delete_builtin_group():
    bg = call("group.query", [["builtin", "=", True]])[0]
    with pytest.raises(CallError) as ve:
        call("group.delete", bg["id"])

    assert "built-in group cannot be deleted" in ve.value.errmsg


def test_update_builtin_group_userns_idmap_forbidden():
    bg = call("group.query", [["builtin", "=", True]])[0]
    with pytest.raises((ValidationErrors, CallError)) as ve:
        call("group.update", bg["id"], {"userns_idmap": "DIRECT"})

    assert "builtin accounts" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# userns_idmap
# ---------------------------------------------------------------------------
def test_create_group_userns_idmap_direct():
    with group({"name": "covgidmap", "userns_idmap": "DIRECT"}) as g:
        assert g["userns_idmap"] == "DIRECT"
        assert call("group.get_instance", g["id"])["userns_idmap"] == "DIRECT"


def test_group_userns_idmap_conflict():
    with group({"name": "covgidmapa", "userns_idmap": 600000}):
        with pytest.raises(ValidationErrors) as ve:
            with group({"name": "covgidmapb", "userns_idmap": 600000}):
                pass

        assert "already maps to container GID" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# group.get_group_obj
# ---------------------------------------------------------------------------
def test_get_group_obj_no_arguments():
    with pytest.raises(ValidationErrors) as ve:
        call("group.get_group_obj", {})

    assert 'Either "groupname" or "gid" must be specified' in str(ve.value), ve.value


def test_get_group_obj_both_arguments():
    with pytest.raises(ValidationErrors) as ve:
        call("group.get_group_obj", {"groupname": "root", "gid": 0})

    assert '"groupname" and "gid" may not be simultaneously specified' in str(ve.value), ve.value


def test_get_group_obj_nonexistent_name():
    with pytest.raises(Exception) as ve:
        call("group.get_group_obj", {"groupname": "cov_nonexistent_group_xyz"})

    assert "group with this name does not exist" in str(ve.value)


def test_get_group_obj_nonexistent_gid():
    with pytest.raises(Exception) as ve:
        call("group.get_group_obj", {"gid": 88888})

    assert "group with this id does not exist" in str(ve.value)


def test_get_group_obj_sid_info_local():
    with group({"name": "covsidgroup"}) as g:
        obj = call("group.get_group_obj", {"groupname": "covsidgroup", "sid_info": True})
        assert obj["source"] == "LOCAL"
        assert obj["local"] is True
        assert obj["gr_gid"] == g["gid"]


# ---------------------------------------------------------------------------
# SMB group-name conflicts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["administrators", "guests", "users"])
def test_create_smb_group_conflicts_with_smb_builtin(name):
    with pytest.raises(ValidationErrors) as ve:
        call("group.create", {"name": name, "smb": True})

    assert "conflicts with existing SMB Builtin entry" in str(ve.value), ve.value


def test_create_smb_group_case_insensitive_conflict():
    with group({"name": "CovSmbGrp", "smb": True}):
        with pytest.raises(ValidationErrors) as ve:
            call("group.create", {"name": "covsmbgrp", "smb": True})

        # Either the groupmap conflict or the duplicate-name check fires.
        assert "conflicts with existing groupmap entry" in str(ve.value) or \
            "already exists" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# userns_idmap on a privileged group is rejected
# ---------------------------------------------------------------------------
def test_update_privileged_group_userns_idmap_forbidden():
    with group({"name": "covprivgrp", "smb": False}) as g:
        with privilege({
            "name": "Cov Priv",
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }):
            with pytest.raises(ValidationErrors) as ve:
                call("group.update", g["id"], {"userns_idmap": "DIRECT"})

            assert "privileged accounts" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# duplicate GID
# ---------------------------------------------------------------------------
def test_create_group_duplicate_gid():
    with group({"name": "covgida", "gid": 59200, "smb": False}):
        with pytest.raises(ValidationErrors) as ve:
            call("group.create", {"name": "covgidb", "gid": 59200, "smb": False})

        assert "Gid 59200 is already used" in str(ve.value), ve.value


# ---------------------------------------------------------------------------
# group.do_update mutation paths
# ---------------------------------------------------------------------------
# NOTE: the `data.pop('gid')` branch in group.do_update is unreachable from the
# API because `gid` is excluded from the GroupUpdate model (group.update rejects
# it with "Extra inputs are not permitted").
def test_update_builtin_group_field_forbidden():
    bu = call("group.query", [["group", "=", "builtin_users"]], {"get": True})
    with pytest.raises(ValidationErrors) as ve:
        call("group.update", bu["id"], {"smb": not bu["smb"]})

    assert "may not be changed for builtin groups" in str(ve.value), ve.value


def test_smb_group_rename():
    with group({"name": "covsmbrename", "smb": True}) as g:
        call("group.update", g["id"], {"name": "covsmbrenamed"})
        assert call("group.get_instance", g["id"])["name"] == "covsmbrenamed"


def test_group_toggle_smb():
    with group({"name": "covtogsmb", "smb": False}) as g:
        call("group.update", g["id"], {"smb": True})
        assert call("group.get_instance", g["id"])["smb"] is True
        call("group.update", g["id"], {"smb": False})
        assert call("group.get_instance", g["id"])["smb"] is False
