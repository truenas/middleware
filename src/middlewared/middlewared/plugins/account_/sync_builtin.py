from collections import defaultdict
import os
import pkg_resources

from middlewared.service import private, Service
from middlewared.utils import osc


def read_file(path):
    with open(path) as f:
        return list(filter(None, f.read().strip().split("\n")))


class UserService(Service):

    @private
    def sync_builtin(self):
        smb_builtins = [
            'builtin_administrators',
            'builtin_users',
            'builtin_guests',
        ]
        remove_groups = {
            group["group"]: group
            for group in self.middleware.call_sync(
                "datastore.query",
                "account.bsdgroups",
                [("builtin", "=", True)],
                {"prefix": "bsdgrp_"},
            )
        }
        remove_users = {
            user["username"]: user
            for user in self.middleware.call_sync(
                "datastore.query",
                "account.bsdusers",
                [
                    ("builtin", "=", True)
                ],
                {"prefix": "bsdusr_"},
            )
        }

        path = pkg_resources.resource_filename("middlewared", f"assets/account/builtin/{osc.SYSTEM.lower()}")
        group_file = []
        passwd_file = []
        if osc.IS_LINUX:
            group_file += read_file("/conf/base/etc/group")
            passwd_file += read_file("/conf/base/etc/passwd")
        group_file += read_file(os.path.join(path, "group"))
        passwd_file += read_file(os.path.join(path, "passwd"))

        # Insert new groups or update GID for existing groups

        groups_members = defaultdict(set)
        for name, _, gid, members in map(lambda s: s.split(":", 3), group_file):
            gid = int(gid)

            existing_group = remove_groups.pop(name, None)
            if existing_group is not None:
                if existing_group["gid"] != gid:
                    self.logger.info("Changing group %r GID from %r to %r", existing_group["group"],
                                     existing_group["gid"], gid)
                    self.middleware.call_sync(
                        "datastore.update",
                        "account.bsdgroups",
                        existing_group["id"],
                        {
                            "gid": gid,
                        },
                        {"prefix": "bsdgrp_"},
                    )
            else:
                self.logger.info("Creating new group %r", name)
                existing_group = {
                    "gid": gid,
                    "group": name,
                    "builtin": True,
                    "sudo": False,
                    "smb": True if name in smb_builtins else False,
                    "sudo_commands": [],
                    "sudo_nopasswd": False,
                }
                existing_group["id"] = self.middleware.call_sync(
                    "datastore.insert",
                    "account.bsdgroups",
                    existing_group,
                    {"prefix": "bsdgrp_"},
                )

            for username in list(filter(None, members.split(","))):
                groups_members[username].add(existing_group["id"])

        # Remove gone groups

        remove_groups = list(remove_groups.values())
        if remove_groups:
            self.logger.info("Removing groups %r", [group["group"] for group in remove_groups])

            remove_group_ids = [group["id"] for group in remove_groups]

            nogroup_id = self.middleware.call_sync(
                "datastore.query",
                "account.bsdgroups",
                [("group", "=", "nogroup")],
                {
                    "get": True,
                    "prefix": "bsdgrp_",
                },
            )["id"]

            for user in self.middleware.call_sync(
                "datastore.query",
                "account.bsdusers",
                [
                    ("group_id", "in", remove_group_ids),
                ],
                {"prefix": "bsdusr_"},
            ):
                self.middleware.call_sync(
                    "datastore.update",
                    "account.bsdusers",
                    user["id"],
                    {
                        "group_id": nogroup_id,
                    },
                    {"prefix": "bsdusr_"},
                )

            self.middleware.call_sync(
                "datastore.delete",
                "account.bsdgroups",
                [("id", "in", remove_group_ids)],
            )

        # Insert new users or update GID for existing groups

        for name, _, uid, gid, gecos, home, shell in map(lambda s: s.split(":", 6), passwd_file):
            uid = int(uid)
            gid = int(gid)

            group = self.middleware.call_sync(
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
                existing_user = self.middleware.call_sync(
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

                update = {}

                if existing_user["uid"] != uid:
                    self.logger.info("Changing user %r UID from %r to %r", existing_user["username"],
                                     existing_user["uid"], uid)
                    update["uid"] = uid

                if existing_user["group"]["bsdgrp_gid"] != gid:
                    self.logger.info("Changing user %r group from %r to %r", existing_user["username"],
                                     existing_user["group"]["bsdgrp_group"], group["group"])
                    update["group"] = group["id"]

                if update:
                    self.middleware.call_sync(
                        "datastore.update",
                        "account.bsdusers",
                        existing_user["id"],
                        update,
                        {"prefix": "bsdusr_"},
                    )
            else:
                self.logger.info("Creating new user %r", name)
                existing_user = {
                    "uid": uid,
                    "username": name,
                    "home": home,
                    "shell": shell,
                    "full_name": gecos,
                    "builtin": True,
                    "microsoft_account": False,
                    "group": group["id"],
                    "attributes": {},
                    "smb": False,
                    "sudo_commands": [],
                    "sudo_nopasswd": False,
                }
                existing_user["id"] = self.middleware.call_sync(
                    "datastore.insert",
                    "account.bsdusers",
                    existing_user,
                    {"prefix": "bsdusr_"},
                )

            for group_id in groups_members[name]:
                if not self.middleware.call_sync(
                    "datastore.query",
                    "account.bsdgroupmembership",
                    [
                        ("group", "=", group_id),
                        ("user", "=", existing_user["id"]),
                    ],
                    {"prefix": "bsdgrpmember_"},
                ):
                    self.logger.info("Adding user %r to group %r", name, group_id)
                    self.middleware.call_sync(
                        "datastore.insert",
                        "account.bsdgroupmembership",
                        {
                            "group": group_id,
                            "user": existing_user["id"]
                        },
                        {"prefix": "bsdgrpmember_"},
                    )

        # Remove gone users

        remove_users = list(remove_users.values())
        if remove_users:
            self.logger.info("Removing users %r", [user["username"] for user in remove_users])

            remove_user_ids = [user["id"] for user in remove_users]

            self.middleware.call_sync(
                "datastore.delete",
                "account.bsdusers",
                [("id", "in", remove_user_ids)],
            )
