from middlewared.api import api_method
from middlewared.api.current import GroupHasPasswordEnabledUserArgs, GroupHasPasswordEnabledUserResult
from middlewared.plugins.account import unixhash_is_valid
from middlewared.service import Service, private


class GroupService(Service):

    @api_method(GroupHasPasswordEnabledUserArgs, GroupHasPasswordEnabledUserResult, roles=['ACCOUNT_READ'])
    async def has_password_enabled_user(self, gids, exclude_user_ids):
        """
        Checks whether at least one local user with a password is a member of any of the `group_ids`.
        """
        return len(await self.get_password_enabled_users(gids, exclude_user_ids)) > 0

    @private
    async def get_password_enabled_users(self, gids, exclude_user_ids, groups=None):
        if groups is None:
            groups = await self.middleware.call("group.query", [["local", "=", True]])

        result = []
        result_user_ids = set()
        group_ids = {g["id"] for g in groups if g["gid"] in gids}

        for membership in await self.middleware.call(
            "datastore.query",
            "account.bsdgroupmembership",
            [
                ["OR", [
                    ["group", "in", group_ids],
                    ["user.bsdusr_group", "in", group_ids],  # primary group
                ]],
                ["user", "nin", set(exclude_user_ids)],
            ],
            {"prefix": "bsdgrpmember_"},
        ):
            if membership["user"]["id"] in result_user_ids:
                continue

            if membership["user"]["bsdusr_locked"]:
                continue

            if membership["user"]["bsdusr_password_disabled"]:
                continue

            if not unixhash_is_valid(membership["user"]["bsdusr_unixhash"]):
                continue

            result.append({k.removeprefix("bsdusr_"): v for k, v in membership["user"].items()})
            result_user_ids.add(membership["user"]["id"])

        return result
