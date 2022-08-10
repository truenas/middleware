import errno

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import group
from middlewared.test.integration.utils import call


def test_change_local_administrator_groups_to_invalid():
    operator = call("group.query", [["group", "=", "operator"]], {"get": True})

    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", 1, {"local_groups": [operator["id"]]})

    assert ve.value.errors[0].attribute == "privilege_update.local_groups"


def test_change_local_administrator_allowlist():
    with pytest.raises(ValidationErrors) as ve:
        call("privilege.update", 1, {"allowlist": [{"method": "CALL", "resource": "system.info"}]})

    assert ve.value.errors[0].attribute == "privilege_update.allowlist"


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
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
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

        assert ve.value.errmsg.startswith("This group has built-in privilege 'Local Administrator'")

        call("privilege.update", 1, {"local_groups": local_groups})
