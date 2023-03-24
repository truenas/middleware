import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import group, user
from middlewared.test.integration.utils import call


def test_shell_choices_has_no_privileges():
    with group({
        "name": "test_no_privileges",
    }) as g:
        assert "/usr/bin/cli" not in call("user.shell_choices", [g["id"]])


def test_shell_choices_has_privileges():
    with group({
        "name": "test_has_privileges",
    }) as g:
        privilege = call("privilege.create", {
            "name": "Test",
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        })
        try:
            assert "/usr/bin/cli" in call("user.shell_choices", [g["id"]])
        finally:
            call("privilege.delete", privilege["id"])


@pytest.mark.parametrize("group_payload", [
    lambda g: {"group": g["id"]},
    lambda g: {"group_create": True, "groups": [g["id"]]},
])
def test_cant_create_user_with_cli_shell_without_privileges(group_payload):
    with group({
        "name": "test_no_privileges",
    }) as g:
        with pytest.raises(ValidationErrors) as ve:
            with user({
                "username": "test",
                "full_name": "Test",
                "home": f"/nonexistent",
                "password": "test1234",
                "shell": "/usr/bin/cli",
                **group_payload(g),
            }):
                pass

        assert ve.value.errors[0].attribute == "user_create.shell"


@pytest.mark.parametrize("group_payload", [
    lambda g: {"group": g["id"]},
    lambda g: {"group_create": True, "groups": [g["id"]]},
])
def test_can_create_user_with_cli_shell_with_privileges(group_payload):
    with group({
        "name": "test_no_privileges",
    }) as g:
        privilege = call("privilege.create", {
            "name": "Test",
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        })
        try:
            with user({
                "username": "test",
                "full_name": "Test",
                "home": f"/nonexistent",
                "password": "test1234",
                "shell": "/usr/bin/cli",
                **group_payload(g),
            }):
                pass
        finally:
            call("privilege.delete", privilege["id"])


@pytest.mark.parametrize("group_payload", [
    lambda g: {"group": g["id"]},
    lambda g: {"groups": [g["id"]]},
])
def test_cant_update_user_with_cli_shell_without_privileges(group_payload):
    with group({
        "name": "test_no_privileges",
    }) as g:
        with user({
            "username": "test",
            "full_name": "Test",
            "home": f"/nonexistent",
            "password": "test1234",
            "group_create": True,
        }) as u:
            with pytest.raises(ValidationErrors) as ve:
                call("user.update", u["id"], {
                    "shell": "/usr/bin/cli",
                    **group_payload(g),
                })

            assert ve.value.errors[0].attribute == "user_update.shell"


@pytest.mark.parametrize("group_payload", [
    lambda g: {"group": g["id"]},
    lambda g: {"groups": [g["id"]]},
])
def test_can_update_user_with_cli_shell_with_privileges(group_payload):
    with group({
        "name": "test_no_privileges",
    }) as g:
        privilege = call("privilege.create", {
            "name": "Test",
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        })
        try:
            with user({
                "username": "test",
                "full_name": "Test",
                "home": f"/nonexistent",
                "password": "test1234",
                "group_create": True,
            }) as u:
                call("user.update", u["id"], {
                    "shell": "/usr/bin/cli",
                    **group_payload(g),
                })
        finally:
            call("privilege.delete", privilege["id"])
