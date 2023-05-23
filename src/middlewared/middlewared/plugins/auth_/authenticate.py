import crypt
import hmac

import pam

from middlewared.service import CallError, Service, private


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    async def authenticate(self, username, password):
        # root and admin must always be local
        # since they may be used by system processes we
        # optimize away the more complex translate_username call
        if username == 'root' or 'username' == 'admin':
            local = True

        else:
            try:
                # We should use this method to translate username to make sure all the different variations
                # of ad usernames are properly handled as the old logic was not taking them into account
                user = await self.middleware.call('user.translate_username', username)
            except CallError:
                local = True
            else:
                username = user['username']
                local = user['local']

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
        try:
            user = await self.middleware.call('user.get_user_obj', {**query, 'get_groups': True})
        except KeyError:
            return None

        groups = set(user['grouplist'])
        groups_key = 'local_groups' if local else 'ds_groups'

        privileges = await self.middleware.call('privilege.privileges_for_groups', groups_key, groups)
        if not privileges:
            return None

        return {
            'username': user['pw_name'],
            'privilege': await self.middleware.call('privilege.compose_privilege', privileges),
        }

    @private
    async def authenticate_root(self):
        return {
            'username': 'root',
            'privilege': await self.middleware.call('privilege.full_privilege'),
        }
