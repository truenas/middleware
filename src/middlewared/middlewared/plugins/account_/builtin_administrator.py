from middlewared.schema import accepts, Int, List
from middlewared.service import filter_list, Service, private


class GroupService(Service):

    @accepts(
        List("gids", items=[Int("gid")]),
        List("exclude_user_ids", items=[Int("exclude_user_id")]),
    )
    async def has_password_enabled_user(self, gids, exclude_user_ids):
        """
        Checks whether at least one local user with a password is a member of any of the `group_ids`.
        """
        return len(await self.get_password_enabled_users(gids, exclude_user_ids)) > 0

    @private
    async def get_password_enabled_users(self, gids, exclude_user_ids, groups=None):
        if groups is None:
            groups = await self.middleware.call('group.query')

        result = []

        groups = filter_list(groups, [["gid", "in", gids]])
        for membership in await self.middleware.call(
            "datastore.query",
            "account.bsdgroupmembership",
            [
                ["group", "in", [g["id"] for g in groups]],
                ["user", "nin", set(exclude_user_ids)],
            ],
            {"prefix": "bsdgrpmember_"}
        ):
            if membership["user"]["bsdusr_locked"]:
                continue

            if membership["user"]["bsdusr_password_disabled"]:
                continue

            if membership["user"]["bsdusr_unixhash"] in ("x", "*"):
                continue

            result.append({k.removeprefix("bsdusr_"): v for k, v in membership["user"].items()})

        return result
