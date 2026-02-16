from middlewared.service import Service, private
from middlewared.service_exception import MatchNotFound


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    async def authenticate_user(self, user):
        """
        Return information for middleware credential based on the specified `user`.
        This is currently called from one of two places:
        1. auth.authenticate_plain -- implements username + password or API key authentication
           for remote users.
        2. check_permission (plugins/auth.py) called by `core.on_connect` for AF_UNIX based sessions.

        Params:
            user: fully populated passwd dict containing optional `grouplist` key
            cred_tag: optional parameter for account-related tags

        Returns:
            Either None type (indicating no middleware credential) or dict containing cred information

        Raises:
            None - This method should not raise exceptions
        """
        try:
            # Grab extended information about the user account from our database. This
            # includes whether account has 2FA enabled
            user_info = await self.middleware.call('user.query', [['username', '=', user['pw_name']]], {'get': True})
        except MatchNotFound:
            # This can happen if there were manual edits to the /etc/passwd file to add a local user unexpectedly
            self.logger.error('%s: user.query failed for username. Denying access', user['pw_name'])
            return None

        if user_info['uid'] != user['pw_uid']:
            # For some reason there's a mismatch between the passwd file
            # and what is stored in the TrueNAS configuration.
            self.logger.error(
                '%s: rejecting access for local user due to uid [%d] not '
                'matching expected value [%d]',
                user['pw_name'], user['pw_uid'], user_info['uid']
            )
            return None

        if user['local'] != user_info['local']:
            # There is a disagreement between our expectation of user account source
            # based on our database and what NSS _actually_ returned.
            self.logger.error(
                '%d: Rejecting access by user id due to potential collision between '
                'local and directory service user account. TrueNAS configuration '
                'expected a %s user account but received an account provided by %s.',
                user['pw_uid'], 'local' if user_info['local'] else 'non-local', user['source']
            )
            return None

        groups_key = 'local_groups' if user['local'] else 'ds_groups'
        groups = set(user['grouplist'])
        privileges = await self.middleware.call('privilege.privileges_for_groups', groups_key, groups)
        if not privileges:
            return None

        return {
            'username': user['pw_name'],
            'account_attributes': user['account_attributes'],
            'privilege': await self.middleware.call('privilege.compose_privilege', privileges),
        }

    @private
    async def authenticate_root(self):
        return {
            'username': 'root',
            'account_attributes': ['LOCAL', 'SYS_ADMIN'],
            'privilege': await self.middleware.call('privilege.full_privilege'),
        }
