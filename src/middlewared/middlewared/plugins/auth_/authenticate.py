import os

from middlewared.service import Service, pass_app, private
from middlewared.service_exception import MatchNotFound
from middlewared.utils.account.oath import OATH_FILE
from truenas_pypam import PAMCode


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    @pass_app(require=True)
    async def authenticate_plain(self, app, username, password):
        user_token = None
        pam_resp = await self.middleware.call('auth.libpam_authenticate', username, password, app=app)
        if pam_resp['code'] == PAMCode.PAM_SUCCESS:
            user_token = await self.authenticate_user(pam_resp['user_info'])
            if user_token is None:
                # Some error occurred when trying to generate our user token
                pam_resp['code'] = PAMCode.PAM_AUTH_ERR
                pam_resp['reason'] = 'Failed to generate user token'

        return {'pam_response': pam_resp, 'user_data': user_token}

    @private
    @pass_app(require=True)
    def libpam_authenticate(self, app, username, password):
        """
        Following PAM codes are returned:

        PAM_SUCCESS = 0
        PAM_SYSTEM_ERR = 4 // pam_tdb.so response if used in unexpected pam service file
        PAM_AUTH_ERR = 7 // Bad username or password
        PAM_AUTHINFO_UNAVAIL = 9 // API key - pam_tdb file must be regenerated
        PAM_USER_UNKNOWN = 10 // API key - user has no keys defined
        PAM_NEW_AUTHTOK_REQD = 12 // User must change password

        Potentially other may be returned as well depending on the particulars
        of the PAM modules.
        """
        auth_ctx = app.authentication_context
        if auth_ctx.pam_hdl is None:
            raise RuntimeError('pam handle was not initialized')

        # Protect against the PAM service file not existing. By default PAM will fallthrough
        # if the service file doesn't exist. We want to try to etc.generate, and if that fails,
        # error out cleanly.
        if not os.path.exists(os.path.join('/etc/pam.d/', auth_ctx.pam_hdl.state.service)):
            self.logger.error('PAM service file is missing. Attempting to regenerate')
            self.middleware.call_sync('etc.generate', 'pam_middleware')
            if not os.path.exists(os.path.join('/etc/pam.d/', auth_ctx.pam_hdl.state.service)):
                self.logger.error(
                    '%s: Unable to generate PAM service file for middleware. Denying '
                    'access to user.', username
                )
                return {'code': PAMCode.PAM_ABORT, 'reason': 'Failed to generate PAM service file', 'user_info': None}

        if not os.path.exists(OATH_FILE):
            self.middleware.call_sync('etc.generate', 'user')

        resp = auth_ctx.pam_hdl.authenticate(username, password)
        return {'code': resp.code, 'reason': resp.reason, 'user_info': resp.user_info}

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
