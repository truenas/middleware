from middlewared.api import api_method
from middlewared.api.current import GroupHasPasswordEnabledUserArgs, GroupHasPasswordEnabledUserResult
from middlewared.plugins.account import unixhash_is_valid
from middlewared.service import filter_list, Service, private


class GroupService(Service):

    @api_method(GroupHasPasswordEnabledUserArgs, GroupHasPasswordEnabledUserResult, roles=['ACCOUNT_READ'])
    async def has_password_enabled_user(self, gids, exclude_user_ids):
        """
        Checks if at least one local user with a password is a member of any of the given groups.
        """
        return len(await self.get_password_enabled_users(gids, exclude_user_ids)) > 0

    @private
    async def get_password_enabled_users(self, gids, exclude_user_ids, groups=None):
        """
        :param groups: List of group entries to check.
        """
        if groups is None:
            groups = await self.middleware.call("group.query", [["gid", "in", gids]])
        else:
            groups = filter_list(groups, [["gid", "in", gids]])

        result = []
        result_user_ids = set()

        for membership in await self.middleware.call(
            "datastore.query",
            "account.bsdgroupmembership",
            [
                ["group", "in", [g["id"] for g in groups]],
                ["user", "nin", set(exclude_user_ids)],
            ],
            {"prefix": "bsdgrpmember_"}
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
