"""Updating one field must not re-validate stored state that the request leaves alone."""
import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import group, user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, ssh


def _user(**overrides):
    return {
        "username": "covreval",
        "full_name": "cov revalidation",
        "group_create": True,
        "smb": False,
        "password": "test1234",
        **overrides,
    }


def test_update_user_whose_sudo_command_disappeared():
    ssh("install -m 755 /dev/null /root/covreval-sudo.sh")
    try:
        with user(_user(sudo_commands=["/root/covreval-sudo.sh"])) as u:
            ssh("rm /root/covreval-sudo.sh")

            call("user.update", u["id"], {"full_name": "cov renamed"})

            with pytest.raises(ValidationErrors) as ve:
                call("user.update", u["id"], {"sudo_commands": ["/root/covreval-sudo.sh", "/usr/bin/ls"]})

            assert ve.value.errors[0].attribute == "user_update.sudo_commands.0", ve.value
    finally:
        ssh("rm -f /root/covreval-sudo.sh")


def test_update_idmap_user_after_its_group_was_granted_a_privilege():
    with group({"name": "covrevalpriv", "smb": False}) as g:
        with user(_user(groups=[g["id"]], userns_idmap="DIRECT")) as u:
            with privilege({
                "name": "Cov revalidation",
                "local_groups": [g["gid"]],
                "ds_groups": [],
                "roles": ["READONLY_ADMIN"],
                "web_shell": False,
            }):
                call("user.update", u["id"], {"full_name": "cov renamed"})

                with pytest.raises(ValidationErrors) as ve:
                    call("user.update", u["id"], {"userns_idmap": 5000})

                assert "privileged accounts" in str(ve.value), ve.value


def test_update_root_with_legacy_extra_group():
    root = call("user.query", [["uid", "=", 0]], {"get": True})
    with group({"name": "covrevalroot", "smb": False}) as g:
        call(
            "datastore.insert",
            "account.bsdgroupmembership",
            {"group": g["id"], "user": root["id"]},
            {"prefix": "bsdgrpmember_"},
        )
        try:
            assert g["id"] in call("user.get_instance", root["id"])["groups"]

            call("user.update", root["id"], {"full_name": root["full_name"]})

            with pytest.raises(ValidationErrors) as ve:
                call("user.update", root["id"], {"groups": [g["id"]]})

            assert "builtin_administrators" in str(ve.value), ve.value
        finally:
            call("user.update", root["id"], {"groups": root["groups"]})


def test_update_user_with_legacy_idmap_conflict():
    with user(_user(username="covrevalidmapa", userns_idmap=4100)):
        with user(_user(username="covrevalidmapb", userns_idmap=4101)) as b:
            call("datastore.update", "account.bsdusers", b["id"], {"bsdusr_userns_idmap": 4100})

            call("user.update", b["id"], {"full_name": "cov renamed"})


def test_update_legacy_ssh_password_user_with_default_home():
    with dataset("covrevalssh") as ds:
        with user(_user(home=f"/mnt/{ds}", home_create=True, ssh_password_enabled=True)) as u:
            call("datastore.update", "account.bsdusers", u["id"], {"bsdusr_home": "/var/empty"})

            call("user.update", u["id"], {"locked": True})

            assert call("user.get_instance", u["id"])["locked"] is True


def test_moving_ssh_password_user_to_default_home_reports_home_only():
    with dataset("covrevalsshmv") as ds:
        with user(_user(home=f"/mnt/{ds}", home_create=True, ssh_password_enabled=True)) as u:
            with pytest.raises(ValidationErrors) as ve:
                call("user.update", u["id"], {"home": "/var/empty"})

            assert [e.attribute for e in ve.value.errors] == ["user_update.home"], ve.value
