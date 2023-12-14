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
        if username in ('root', 'admin'):
            local = True

        else:
            local = bool(await self.middleware.call(
                'datastore.query',
                'account.bsdusers',
                [('username', '=', username)],
                {'prefix': 'bsdusr_', 'count': True},
            ))

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
            user = await self.middleware.call('user.get_user_obj', {**query, 'get_groups': True, 'sid_info': not local})
        except KeyError:
            return None

        twofactor_enabled = bool((await self.middleware.call(
            'auth.twofactor.get_user_config',
            user['pw_uid'] if local else user['sid_info']['sid'],
            local
        ))['secret'])

        groups = set(user['grouplist'])
        groups_key = 'local_groups' if local else 'ds_groups'

        account_flags = []

        if local:
            account_flags.append('LOCAL')
        else:
            account_flags.append('DIRECTORY_SERVICE')
            if user['sid_info']['domain_information']['activedirectory']:
                account_flags.append('ACTIVE_DIRECTORY')
            else:
                account_flags.append('LDAP')

        if twofactor_enabled:
            account_flags.append('2FA')

        if user['pw_uid'] in (0, 950):
            account_flags.append('SYS_ADMIN')

        privileges = await self.middleware.call('privilege.privileges_for_groups', groups_key, groups)
        if not privileges:
            return None

        return {
            'username': user['pw_name'],
            'account_attributes': account_flags,
            'privilege': await self.middleware.call('privilege.compose_privilege', privileges),
        }

    @private
    async def authenticate_root(self):
        return {
            'username': 'root',
            'account_attributes': ['LOCAL', 'SYS_ADMIN'],
            'privilege': await self.middleware.call('privilege.full_privilege'),
        }
