import errno

from middlewared.service import CallError, private, Service


class UserService(Service):

    SYS_USERS = {}

    @private
    async def get_internal_user_id(self, username):
        if not self.SYS_USERS:
            UserService.SYS_USERS = {
                u['username']: u['uid'] for u in await self.middleware.call(
                    'user.query', [['builtin', '=', True]], {'force_sql_filters': True}
                )
            }
        try:
            return self.SYS_USERS[username]
        except KeyError:
            raise CallError(f'{username!r} user not found', errno.ENOENT)


class GroupService(Service):

    SYS_GROUPS = {}

    @private
    async def get_internal_group_id(self, group_name):
        if not self.SYS_GROUPS:
            GroupService.SYS_GROUPS = {
                g['group']: g['gid'] for g in await self.middleware.call(
                    'group.query', [['builtin', '=', True]], {'force_sql_filters': True}
                )
            }
        try:
            return self.SYS_GROUPS[group_name]
        except KeyError:
            raise CallError(f'{group_name!r} group not found', errno.ENOENT)
