import crypt
import hmac

import pam

from middlewared.service import CallError, internal, Service, pass_app, private


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    async def authenticate(self, username, password):
        if user_info := (await self.middleware.call(
            'datastore.query', 'account.bsdusers',
            [('username', '=', username)],
            {'prefix': 'bsdusr_', 'select': ['id', 'unixhash', 'uid']},
        )):
            user_info = user_info[0] | {'local': True}
            unixhash = user_info.pop('unixhash')
        else:
            user_info = {'id': None, 'uid': None, 'local': False}
            unixhash = None

        # The following provides way for root user to avoid getting locked out
        # of webui via due to PAM enforcing password policies on the root
        # account. Specifically, some legacy users have configured the root
        # account so its password has password_disabled = true. We have to
        # maintain the old middleware authentication code (bypassing PAM) to
        # prevent this.
        #
        # In all failure cases libpam_authenticate is called so that timing
        # is consistent with pam_fail_delay
        if username == 'root' and await self.middleware.call('privilege.always_has_root_password_enabled'):
            if unixhash in ('x', '*'):
                await self.middleware.call('auth.libpam_authenticate', username, password)
                return None

            if not await self.middleware.call('auth.check_unixhash', password, unixhash):
                await self.middleware.call('auth.libpam_authenticate', username, password)
                return None

        elif not await self.middleware.call('auth.libpam_authenticate', username, password):
            return None

        return await self.authenticate_user({'username': username}, user_info)

    @internal
    def check_unixhash(self, password, unixhash):
        # This method is vulnerable to timing attacks and so should not
        # be exposed to external API consumers in any way.
        if unixhash in ('x', '*'):
            return False

        return hmac.compare_digest(crypt.crypt(password, unixhash), unixhash)

    @private
    def libpam_authenticate(self, username, password):
        p = pam.pam()
        return p.authenticate(username, password, service='middleware')

    @private
    async def authenticate_user(self, query, user_info):
        try:
            user = await self.middleware.call('user.get_user_obj', {
                **query, 'get_groups': True,
                'sid_info': not user_info['local'],
            })
        except KeyError:
            return None

        if user_info['uid'] is not None and user_info['uid'] != user['pw_uid']:
            # For some reason there's a mismatch between the passwd file
            # and what is stored in the TrueNAS configuration.
            self.logger.error(
                '%s: rejecting access for local user due to uid [%d] not '
                'matching expected value [%d]',
                user['pw_name'], user['pw_uid'], user_info['uid']
            )
            return None

        if user_info['local']:
            twofactor_id = user_info['id']
            groups_key = 'local_groups'
            account_flags = ['LOCAL']
        else:
            twofactor_id = user['sid_info']['sid']
            groups_key = 'ds_groups'
            account_flags = ['DIRECTORY_SERVICE']
            if user['sid_info']['domain_information']['activedirectory']:
                account_flags.append('ACTIVE_DIRECTORY')
            else:
                account_flags.append('LDAP')

        # Two-factor authentication token is keyed by SID for activedirectory
        # users.
        twofactor_id = user_info['id'] if user_info['local'] else user['sid_info']['sid']
        twofactor_enabled = bool((await self.middleware.call(
            'auth.twofactor.get_user_config',
            twofactor_id, user_info['local']
        ))['secret'])

        groups = set(user['grouplist'])

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
