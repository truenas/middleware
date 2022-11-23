import crypt
import hmac

import pam

from middlewared.service import Service, private


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    async def authenticate(self, username, password):
        local = '@' not in username

        if username == 'root' and await self.middleware.call('privilege.always_has_root_password_enabled'):
            root = await self.middleware.call(
                'datastore.query',
                'account.bsdusers',
                [('username', '=', 'root')],
                {'get': True, 'prefix': 'bsdusr_'},
            )

            if root['unixhash'] in ('x', '*'):
                return None

            if not hmac.compare_digest(crypt.crypt(password, root['unixhash']), root['unixhash']):
                return None
        elif not await self.middleware.call('auth.libpam_authenticate', username, password):
            return None

        return await self.authenticate_user({'username': username}, local)

    @private
    def libpam_authenticate(self, username, password):
        p = pam.pam()
        return p.authenticate(username, password, service='middleware')

    @private
    async def authenticate_user(self, query, local):
        user = await self.middleware.call('user.get_user_obj', {**query, 'get_groups': True})
        groups = set(user['grouplist'])
        groups_key = 'local_groups' if local else 'ds_groups'

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
