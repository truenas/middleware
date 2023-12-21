import errno

from middlewared.service import CallError, private, Service


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

    @private
    async def username_to_uid(self, user_name):
        '''
        Return UID of username or None if not found
        NOTE: The lookup can be slow
        '''
        uid = None

        if user_name is not None:
            try:
                user = await self.middleware.call('dscache.get_uncached_user', user_name)
                uid = user['pw_uid']
            except Exception:
                pass

        return uid

    @private
    async def uid_to_username(self, uid):
        '''
        Return username associated with the uid or None if not found
        '''
        user_name = None

        if uid is not None:
            try:
                user = await self.middleware.call('dscache.get_uncached_user', None, uid)
                user_name = user['pw_name']
            except Exception:
                pass

        return user_name


class GroupService(Service):

    SYS_GROUPS = {}

    @private
    async def get_builtin_group_id(self, group_name):
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

    @private
    async def groupname_to_gid(self, group_name):
        '''
        Return GID of groupname or None if not found
        '''
        gid = None

        if group_name is not None:
            try:
                group = await self.middleware.call('dscache.get_uncached_group', group_name)
                gid = group['gr_gid']
            except Exception:
                pass

        return gid

    @private
    async def gid_to_groupname(self, group_id):
        '''
        Return groupname associated with the gid or None if not found
        '''
        group_name = None

        if group_id is not None:
            try:
                group = await self.middleware.call('dscache.get_uncached_group', None, group_id)
                group_name = group['gr_name']
            except Exception:
                pass

        return group_name
