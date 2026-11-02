from __future__ import annotations

from collections import defaultdict
import itertools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("sync_builtin",)

# accounts that should have their userns_idmap field set to DIRECT.
#
# When a new account is added that needs this mapping, its uid / gid
# should be added here to ensure that the field is set appropriately
# on datastore insertion
BUILTIN_USERNS_IDMAP_USER = {568}
BUILTIN_USERNS_IDMAP_GROUP = {568}


def read_file(path: str) -> list[str]:
    with open(path) as f:
        return list(filter(None, f.read().strip().split("\n")))


def sync_builtin(context: ServiceContext) -> None:
    smb_builtins = [
        "builtin_administrators",
        "builtin_users",
        "builtin_guests",
    ]
    remove_groups = {
        group["group"]: group
        for group in context.middleware.call_sync(
            "datastore.query",
            "account.bsdgroups",
            [("builtin", "=", True)],
            {"prefix": "bsdgrp_"},
        )
    }
    remove_users = {
        user["username"]: user
        for user in context.middleware.call_sync(
            "datastore.query",
            "account.bsdusers",
            [("builtin", "=", True)],
            {"prefix": "bsdusr_"},
        )
    }
    non_builtin_groups = {
        group["group"]: group
        for group in context.middleware.call_sync(
            "datastore.query",
            "account.bsdgroups",
            [("builtin", "=", False)],
            {"prefix": "bsdgrp_"},
        )
    }
    non_builtin_users = {
        user["username"]: user
        for user in context.middleware.call_sync(
            "datastore.query",
            "account.bsdusers",
            [("builtin", "=", False)],
            {"prefix": "bsdusr_"},
        )
    }

    group_file = read_file("/conf/base/etc/group")
    passwd_file = read_file("/conf/base/etc/passwd")

    # Insert new groups or update GID for existing groups

    groups_members: defaultdict[str, set[int]] = defaultdict(set)
    for name, _, raw_gid, members in map(lambda s: s.split(":", 3), group_file):
        gid = int(raw_gid)

        if name in non_builtin_groups:
            for i in itertools.count(1):
                new_name = f"{name}_{i}"
                if new_name not in non_builtin_groups:
                    break

            context.logger.info(
                "Renaming non-builtin group %r to %r as builtin group with that name should exist",
                name,
                new_name,
            )
            context.middleware.call_sync(
                "datastore.update",
                "account.bsdgroups",
                non_builtin_groups[name]["id"],
                {
                    "group": new_name,
                },
                {"prefix": "bsdgrp_"},
            )

        existing_group = remove_groups.pop(name, None)
        if existing_group is not None:
            if existing_group["gid"] != gid:
                context.logger.info(
                    "Changing group %r GID from %r to %r", existing_group["group"], existing_group["gid"], gid
                )
                context.middleware.call_sync(
                    "datastore.update",
                    "account.bsdgroups",
                    existing_group["id"],
                    {
                        "gid": gid,
                    },
                    {"prefix": "bsdgrp_"},
                )
        else:
            context.logger.info("Creating new group %r", name)
            existing_group = {
                "gid": gid,
                "group": name,
                "builtin": True,
                "smb": True if name in smb_builtins else False,
                "sudo_commands": [],
                "sudo_commands_nopasswd": [],
                "userns_idmap": "DIRECT" if gid in BUILTIN_USERNS_IDMAP_GROUP else 0,
            }
            existing_group["id"] = context.middleware.call_sync(
                "datastore.insert",
                "account.bsdgroups",
                existing_group,
                {"prefix": "bsdgrp_"},
            )

        for username in list(filter(None, members.split(","))):
            groups_members[username].add(existing_group["id"])

    # Remove gone groups

    gone_groups = list(remove_groups.values())
    if gone_groups:
        context.logger.info("Removing groups %r", [group["group"] for group in gone_groups])

        remove_group_ids = [group["id"] for group in gone_groups]

        nogroup_id = context.middleware.call_sync(
            "datastore.query",
            "account.bsdgroups",
            [("group", "=", "nogroup")],
            {
                "get": True,
                "prefix": "bsdgrp_",
            },
        )["id"]

        for user in context.middleware.call_sync(
            "datastore.query",
            "account.bsdusers",
            [
                ("group_id", "in", remove_group_ids),
            ],
            {"prefix": "bsdusr_"},
        ):
            context.middleware.call_sync(
                "datastore.update",
                "account.bsdusers",
                user["id"],
                {
                    "group_id": nogroup_id,
                },
                {"prefix": "bsdusr_"},
            )

        context.middleware.call_sync(
            "datastore.delete",
            "account.bsdgroups",
            [("id", "in", remove_group_ids)],
        )

    # Insert new users or update GID for existing groups

    for name, _, raw_uid, raw_gid, gecos, home, shell in map(lambda s: s.split(":", 6), passwd_file):
        uid = int(raw_uid)
        gid = int(raw_gid)

        if name in non_builtin_users:
            for i in itertools.count(1):
                new_name = f"{name}_{i}"
                if new_name not in non_builtin_users:
                    break

            context.logger.info(
                "Renaming non-builtin user %r to %r as builtin user with that name should exist",
                name,
                new_name,
            )
            context.middleware.call_sync(
                "datastore.update",
                "account.bsdusers",
                non_builtin_users[name]["id"],
                {
                    "username": new_name,
                },
                {"prefix": "bsdusr_"},
            )

        group = context.middleware.call_sync(
            "datastore.query",
            "account.bsdgroups",
            [("gid", "=", gid)],
            {
                "get": True,
                "prefix": "bsdgrp_",
            },
        )

        existing_user = remove_users.pop(name, None)
        if existing_user is not None:
            # Reload updated GID
            existing_user = context.middleware.call_sync(
                "datastore.query",
                "account.bsdusers",
                [
                    ("id", "=", existing_user["id"]),
                ],
                {
                    "get": True,
                    "prefix": "bsdusr_",
                },
            )

            update: dict[str, Any] = {}

            if existing_user["uid"] != uid:
                context.logger.info(
                    "Changing user %r UID from %r to %r", existing_user["username"], existing_user["uid"], uid
                )
                update["uid"] = uid

            if existing_user["group"]["bsdgrp_gid"] != gid:
                context.logger.info(
                    "Changing user %r group from %r to %r",
                    existing_user["username"],
                    existing_user["group"]["bsdgrp_group"],
                    group["group"],
                )
                update["group"] = group["id"]

            if existing_user["home"] != home:
                update["home"] = home

            if update:
                context.middleware.call_sync(
                    "datastore.update",
                    "account.bsdusers",
                    existing_user["id"],
                    update,
                    {"prefix": "bsdusr_"},
                )
        else:
            context.logger.info("Creating new user %r", name)
            existing_user = {
                "uid": uid,
                "username": name,
                "home": home,
                "shell": shell,
                "full_name": gecos.split(",")[0],
                "builtin": True,
                "group": group["id"],
                "smb": False,
                "sudo_commands": [],
                "sudo_commands_nopasswd": [],
                "userns_idmap": "DIRECT" if uid in BUILTIN_USERNS_IDMAP_USER else 0,
            }
            existing_user["id"] = context.middleware.call_sync(
                "datastore.insert",
                "account.bsdusers",
                existing_user,
                {"prefix": "bsdusr_"},
            )
            context.middleware.call_sync(
                "datastore.insert",
                "account.twofactor_user_auth",
                {
                    "secret": None,
                    "user": existing_user["id"],
                },
            )

        for group_id in groups_members[name]:
            if not context.middleware.call_sync(
                "datastore.query",
                "account.bsdgroupmembership",
                [
                    ("group", "=", group_id),
                    ("user", "=", existing_user["id"]),
                ],
                {"prefix": "bsdgrpmember_"},
            ):
                context.logger.info("Adding user %r to group %r", name, group_id)
                context.middleware.call_sync(
                    "datastore.insert",
                    "account.bsdgroupmembership",
                    {"group": group_id, "user": existing_user["id"]},
                    {"prefix": "bsdgrpmember_"},
                )

    # Remove gone users

    gone_users = list(remove_users.values())
    if gone_users:
        context.logger.info("Removing users %r", [user["username"] for user in gone_users])

        remove_user_ids = [user["id"] for user in gone_users]

        context.middleware.call_sync(
            "datastore.delete",
            "account.bsdusers",
            [("id", "in", remove_user_ids)],
        )
