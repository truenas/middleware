import crypt
import hmac

from middlewared.service import Service, private


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    async def authenticate(self, username, password):
        if '@' in username:
            if (await self.middleware.call('datastore.config', 'system.settings'))['stg_ds_auth']:
                return await self.ds_authenticate(username, password)
            else:
                return None
        else:
            return await self.local_authenticate(username, password)

    @private
    async def local_authenticate(self, username, password):
        try:
            user = await self.middleware.call(
                'datastore.query',
                'account.bsdusers',
                [
                    ('bsdusr_username', '=', username),
                    ('bsdusr_password_disabled', '=', False),
                    ('bsdusr_locked', '=', False),
                ],
                {'get': True},
            )
        except IndexError:
            return None

        if user['bsdusr_unixhash'] in ('x', '*'):
            return None

        if not hmac.compare_digest(crypt.crypt(password, user['bsdusr_unixhash']), user['bsdusr_unixhash']):
            return None

        return await self.authenticate_local_user(user['id'], username)

    @private
    async def authenticate_local_user(self, user_id, username):
        gids = {
            member['bsdgrpmember_group']['bsdgrp_gid']
            for member in await self.middleware.call(
                'datastore.query',
                'account.bsdgroupmembership',
                [['bsdgrpmember_user', '=', user_id]],
            )
        }

        return await self.common_authenticate(username, 'local_groups', gids)

    @private
    async def ds_authenticate(self, username, password):
        return None  # FIXME

    @private
    async def common_authenticate(self, username, groups_key, groups):
        privileges = [
            privilege for privilege in await self.middleware.call('datastore.query', 'account.privilege')
            if set(privilege[groups_key]) & groups
        ]
        if not privileges:
            return None

        return {
            'username': username,
            'privilege': await self.middleware.call('privilege.compose_privilege', privileges),
        }

    @private
    async def authenticate_root(self):
        return {
            'username': 'root',
            'privilege': await self.middleware.call('privilege.full_privilege'),
        }
