"""Tests for `user.sync_builtin`.

It reconciles the built-in accounts in the database with /conf/base/etc/{passwd,group}.
It only runs during migrations, so the drift it repairs is simulated here by editing the
datastore directly.
"""

import pytest

from middlewared.test.integration.utils import call

NO_LOGIN_SHELL = "/usr/sbin/nologin"
# a builtin group that no account uses as its primary group, so its row can be removed
STANDALONE_BUILTIN_GROUP = ("audio", 29)
BUILTIN_GROUP_FILE_ENTRY = ("games", 60)
BUILTIN_USER_FILE_ENTRY = ("games", 5, "/usr/games")
# `dialout:x:20:nut` in /conf/base/etc/group
BUILTIN_GROUP_MEMBERSHIP_FILE_ENTRY = ("dialout", "nut")


@pytest.fixture(scope="module")
def sync_builtin():
    """Refresh the generated files once the simulated drift has been reconciled."""
    yield

    call("user.sync_builtin")
    call("etc.generate", "user")


def _builtin_group(name):
    return call(
        "datastore.query",
        "account.bsdgroups",
        [["group", "=", name]],
        {"get": True, "prefix": "bsdgrp_"},
    )


def _builtin_user(name):
    return call(
        "datastore.query",
        "account.bsdusers",
        [["username", "=", name]],
        {"get": True, "prefix": "bsdusr_"},
    )


def _membership(group_name, username):
    return call(
        "datastore.query",
        "account.bsdgroupmembership",
        [
            ["group.bsdgrp_group", "=", group_name],
            ["user.bsdusr_username", "=", username],
        ],
        {"prefix": "bsdgrpmember_"},
    )


def test_sync_builtin_is_idempotent(sync_builtin):
    groups = call("group.query", [["builtin", "=", True]])
    users = call("user.query", [["builtin", "=", True]])

    call("user.sync_builtin")

    assert call("group.query", [["builtin", "=", True]]) == groups
    assert call("user.query", [["builtin", "=", True]]) == users


def test_sync_builtin_renames_conflicting_non_builtin_group(sync_builtin):
    # A non-builtin group can only hold a builtin name while the builtin group is gone.
    name, gid = STANDALONE_BUILTIN_GROUP
    call("datastore.delete", "account.bsdgroups", _builtin_group(name)["id"])
    ids = [
        call(
            "datastore.insert",
            "account.bsdgroups",
            {
                "group": group_name,
                "gid": group_gid,
                "builtin": False,
                "smb": False,
                "sudo_commands": [],
                "sudo_commands_nopasswd": [],
            },
            {"prefix": "bsdgrp_"},
        )
        for group_name, group_gid in [(name, 61000), (f"{name}_1", 61001)]
    ]
    try:
        call("user.sync_builtin")

        # `name` and `name_1` are taken, so the conflicting group becomes `name_2`
        assert _builtin_group(f"{name}_2")["id"] == ids[0]
        # and the builtin group is re-created
        recreated = _builtin_group(name)
        assert recreated["builtin"] is True
        assert recreated["gid"] == gid
    finally:
        for id_ in ids:
            call("datastore.delete", "account.bsdgroups", id_)


def test_sync_builtin_restores_builtin_group_gid(sync_builtin):
    name, gid = BUILTIN_GROUP_FILE_ENTRY
    call(
        "datastore.update",
        "account.bsdgroups",
        _builtin_group(name)["id"],
        {"gid": 61002},
        {"prefix": "bsdgrp_"},
    )

    call("user.sync_builtin")

    assert _builtin_group(name)["gid"] == gid


def test_sync_builtin_recreates_missing_builtin_group(sync_builtin):
    name, gid = STANDALONE_BUILTIN_GROUP
    call("datastore.delete", "account.bsdgroups", _builtin_group(name)["id"])

    call("user.sync_builtin")

    recreated = _builtin_group(name)
    assert recreated["gid"] == gid
    assert recreated["builtin"] is True


def test_sync_builtin_removes_stale_builtin_entries(sync_builtin):
    group_id = call(
        "datastore.insert",
        "account.bsdgroups",
        {
            "group": "cov_stale_group",
            "gid": 61003,
            "builtin": True,
            "smb": False,
            "sudo_commands": [],
            "sudo_commands_nopasswd": [],
        },
        {"prefix": "bsdgrp_"},
    )
    user_id = call(
        "datastore.insert",
        "account.bsdusers",
        {
            "username": "cov_stale_user",
            "uid": 61003,
            "home": "/var/empty",
            "shell": NO_LOGIN_SHELL,
            "full_name": "cov stale user",
            "builtin": True,
            "group": group_id,
            "smb": False,
            "sudo_commands": [],
            "sudo_commands_nopasswd": [],
        },
        {"prefix": "bsdusr_"},
    )

    call("user.sync_builtin")

    assert call("datastore.query", "account.bsdgroups", [["id", "=", group_id]]) == []
    assert call("datastore.query", "account.bsdusers", [["id", "=", user_id]]) == []


def test_sync_builtin_renames_conflicting_non_builtin_user(sync_builtin):
    # A non-builtin user can only hold a builtin name while the builtin user is gone.
    name, uid, _ = BUILTIN_USER_FILE_ENTRY
    call("datastore.delete", "account.bsdusers", _builtin_user(name)["id"])
    nogroup_id = _builtin_group("nogroup")["id"]
    ids = [
        call(
            "datastore.insert",
            "account.bsdusers",
            {
                "username": username,
                "uid": user_uid,
                "home": "/var/empty",
                "shell": NO_LOGIN_SHELL,
                "full_name": "cov conflicting user",
                "builtin": False,
                "group": nogroup_id,
                "smb": False,
                "sudo_commands": [],
                "sudo_commands_nopasswd": [],
            },
            {"prefix": "bsdusr_"},
        )
        for username, user_uid in [(name, 61004), (f"{name}_1", 61005)]
    ]
    try:
        call("user.sync_builtin")

        # `name` and `name_1` are taken, so the conflicting user becomes `name_2`
        assert _builtin_user(f"{name}_2")["id"] == ids[0]
        # and the builtin user is re-created
        recreated = _builtin_user(name)
        assert recreated["builtin"] is True
        assert recreated["uid"] == uid
    finally:
        for id_ in ids:
            call("datastore.delete", "account.bsdusers", id_)


def test_sync_builtin_restores_builtin_user_attributes(sync_builtin):
    name, uid, home = BUILTIN_USER_FILE_ENTRY
    call(
        "datastore.update",
        "account.bsdusers",
        _builtin_user(name)["id"],
        {
            "uid": 61005,
            "home": "/var/empty",
            "group": _builtin_group("nogroup")["id"],
        },
        {"prefix": "bsdusr_"},
    )

    call("user.sync_builtin")

    entry = _builtin_user(name)
    assert entry["uid"] == uid
    assert entry["home"] == home
    assert entry["group"]["bsdgrp_group"] == name


def test_sync_builtin_recreates_missing_builtin_user(sync_builtin):
    name, uid, _ = BUILTIN_USER_FILE_ENTRY
    call("datastore.delete", "account.bsdusers", _builtin_user(name)["id"])

    call("user.sync_builtin")

    entry = _builtin_user(name)
    assert entry["uid"] == uid
    assert entry["builtin"] is True
    # a fresh account also gets its (empty) two-factor authentication record
    assert call(
        "datastore.query",
        "account.twofactor_user_auth",
        [["user_id", "=", entry["id"]]],
    )


def test_sync_builtin_restores_group_membership(sync_builtin):
    group_name, username = BUILTIN_GROUP_MEMBERSHIP_FILE_ENTRY
    membership = _membership(group_name, username)
    assert len(membership) == 1, membership
    call("datastore.delete", "account.bsdgroupmembership", membership[0]["id"])

    call("user.sync_builtin")

    assert _membership(group_name, username)
