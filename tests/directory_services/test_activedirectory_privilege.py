"""Privileges granted to Active Directory groups.

`privilege.query` resolves `ds_groups` entries, which may be either a GID or a SID, into
group entries. On a stand-alone server every group is local, so the paths where an entry
resolves to an actual domain group are only reachable while joined to a domain; the
stand-alone side (entries that resolve to nothing, or to a local account) lives in
tests/api2/test_account_privilege.py.
"""

import contextlib

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.system import reset_systemd_svcs


@contextlib.contextmanager
def raw_privilege(data):
    """Insert a privilege row directly into the datastore.

    `privilege.create` rejects a domain group in `local_groups`, so this is the only way to
    obtain such a privilege (which is what an administrator ends up with after moving a
    group between the local database and the domain).
    """
    id_ = call(
        "datastore.insert",
        "account.privilege",
        {
            "builtin_name": None,
            "name": "AD test raw",
            "local_groups": [],
            "ds_groups": [],
            "roles": [],
            "web_shell": False,
            **data,
        },
    )
    try:
        yield id_
    finally:
        call("datastore.delete", "account.privilege", id_)


@pytest.fixture(scope="module")
def ad_group():
    """The primary group of the domain account, resolvable by both GID and SID."""
    reset_systemd_svcs("winbind")

    with directoryservice("ACTIVEDIRECTORY") as ad:
        gid = ad["account"].user_obj["pw_gid"]
        entry = call("group.query", [["gid", "=", gid]], {"get": True})
        assert entry["local"] is False, entry
        assert entry["sid"] is not None, entry

        yield entry


def test_privilege_ds_group_by_sid(ad_group):
    with privilege(
        {
            "name": "AD privilege by sid",
            "local_groups": [],
            "ds_groups": [ad_group["sid"]],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }
    ) as p:
        assert p["local_groups"] == []
        assert len(p["ds_groups"]) == 1, p
        assert p["ds_groups"][0]["gid"] == ad_group["gid"]
        assert p["ds_groups"][0]["sid"] == ad_group["sid"]
        assert p["ds_groups"][0]["name"] == ad_group["name"]
        assert p["ds_groups"][0]["local"] is False


def test_privilege_ds_group_by_gid(ad_group):
    """A domain group may also be granted a privilege by GID."""
    with privilege(
        {
            "name": "AD privilege by gid",
            "local_groups": [],
            "ds_groups": [ad_group["gid"]],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }
    ) as p:
        assert len(p["ds_groups"]) == 1, p
        assert p["ds_groups"][0]["gid"] == ad_group["gid"]
        assert p["ds_groups"][0]["sid"] == ad_group["sid"]
        assert p["ds_groups"][0]["local"] is False

        # the GID is what was stored, because that is what was requested
        raw = call(
            "datastore.query",
            "account.privilege",
            [["id", "=", p["id"]]],
            {"get": True},
        )
        assert raw["ds_groups"] == [ad_group["gid"]]


def test_update_privilege_rewrites_ds_group_as_sid(ad_group):
    """`privilege.update` prefers the SID, which is unique across domains."""
    with privilege(
        {
            "name": "AD privilege update",
            "local_groups": [],
            "ds_groups": [ad_group["gid"]],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }
    ) as p:
        updated = call("privilege.update", p["id"], {"name": "AD privilege updated"})

        assert updated["ds_groups"][0]["sid"] == ad_group["sid"]

        raw = call(
            "datastore.query",
            "account.privilege",
            [["id", "=", p["id"]]],
            {"get": True},
        )
        assert raw["ds_groups"] == [ad_group["sid"]]


def test_create_privilege_with_ds_group_as_local_group(ad_group):
    """Only local groups may be granted a privilege through `local_groups`."""
    with pytest.raises(ValidationErrors) as ve:
        call(
            "privilege.create",
            {
                "name": "AD privilege local groups",
                "local_groups": [ad_group["gid"]],
                "ds_groups": [],
                "roles": ["READONLY_ADMIN"],
                "web_shell": False,
            },
        )

    assert ve.value.errors[0].attribute == "privilege_create.local_groups.0"
    assert ve.value.errors[0].errmsg.startswith(f"{ad_group['gid']}: local group does not exist.")


def test_query_privilege_ignores_ds_group_in_local_groups(ad_group):
    """A domain group is never reported as a local group."""
    with raw_privilege({"name": "AD raw local group", "local_groups": [ad_group["gid"]]}) as id_:
        p = call("privilege.get_instance", id_)

        assert p["local_groups"] == []
        assert p["ds_groups"] == []


def test_privileges_for_groups_ds_group(ad_group):
    """A GID from the NSS group list is expanded to its SID before matching privileges."""
    with privilege(
        {
            "name": "AD privilege for groups",
            "local_groups": [],
            "ds_groups": [ad_group["sid"]],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }
    ) as p:
        privileges = call("privilege.privileges_for_groups", "ds_groups", [ad_group["gid"]])

        assert [entry["id"] for entry in privileges] == [p["id"]]

        # the same group grants nothing as a local group
        assert call("privilege.privileges_for_groups", "local_groups", [ad_group["gid"]]) == []
