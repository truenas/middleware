from middlewared.schema import accepts, Int, List
from middlewared.service import Service


class GroupService(Service):

    @accepts(
        List("gids", items=[Int("gid")]),
        List("exclude_user_ids", items=[Int("exclude_user_id")]),
    )
    async def has_password_enabled_user(self, gids, exclude_user_ids):
        """
        Checks whether at least one local user with a password is a member of any of the `group_ids`.
        """
        groups = await self.middleware.call(
            "datastore.query",
            "account.bsdgroups",
            [
                ["gid", "in", gids],
            ],
            {"prefix": "bsdgrp_"},
        )
        for membership in await self.middleware.call(
            "datastore.query",
            "account.bsdgroupmembership",
            [
                ["group", "in", [g["id"] for g in groups]],
                ["user", "nin", set(exclude_user_ids)],
            ],
            {"prefix": "bsdgrpmember_"}
        ):
            if membership["user"]["bsdusr_password_disabled"]:
                continue

            if membership["user"]["bsdusr_unixhash"] == "*":
                continue

            return True

        return False
