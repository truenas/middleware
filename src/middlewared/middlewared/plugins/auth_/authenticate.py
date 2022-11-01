import crypt
import hmac

import pam

from middlewared.service import Service, private


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    async def authenticate(self, username, password):
        if '@' in username:
            if (await self.middleware.call('datastore.config', 'system.settings'))['stg_ds_auth']:
                return await self.ds_authenticate(username.split('@')[0], password)
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
                    ('username', '=', username),
                    ('locked', '=', False),
                ],
                {'get': True, 'prefix': 'bsdusr_'},
            )
        except IndexError:
            return None

        if user['unixhash'] in ('x', '*'):
            return None

        if user['password_disabled']:
            if user['username'] == 'root':
                if not await self.middleware.call('privilege.always_has_root_password_enabled'):
                    return None
            else:
                return None

        if not hmac.compare_digest(crypt.crypt(password, user['unixhash']), user['unixhash']):
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
        if await self.middleware.call('auth.libpam_authenticate', username, password):
            user = await self.middleware.call('user.get_user_obj', {'username': username, 'get_groups': True})
            return await self.common_authenticate(username, 'ds_groups', set(user['grouplist']))

    @private
    def libpam_authenticate(self, username, password):
        p = pam.pam()
        return p.authenticate(username, password)

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
