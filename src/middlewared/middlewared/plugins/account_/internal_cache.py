import errno

from middlewared.service import CallError, Service, private


class UserService(Service):

    SYS_USERS = {}

    @private
    async def get_builtin_user_id(self, username):
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
