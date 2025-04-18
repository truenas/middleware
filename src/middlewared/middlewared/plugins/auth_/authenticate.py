import os
import pam

from middlewared.auth import AuthenticationContext
from middlewared.plugins.account_.constants import (
    ADMIN_UID, MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE
)
from middlewared.service import Service, pass_app, private
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.account.authenticator import TrueNAS_PamAuthenticator
from middlewared.utils.auth import OTPW_MANAGER, OTPWResponse

PAM_SERVICES = {MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE}


class AuthService(Service):

    class Config:
        cli_namespace = 'auth'

    @private
    @pass_app()
    async def authenticate_plain(self, app, username, password, is_api_key=False):
        pam_svc = MIDDLEWARE_PAM_API_KEY_SERVICE if is_api_key else MIDDLEWARE_PAM_SERVICE

        user_token = None
        pam_resp = await self.middleware.call('auth.libpam_authenticate', username, password, pam_svc, app=app)

        # TODO: this needs better integration with PAM. We may have a onetime password (not TOTP token)
        # We perform after failed PAM authentication so that we properly evaluate whether account is disabled
        # This unfortunately means that authentication via onetime password always has pam error delay.
        if pam_resp['code'] == pam.PAM_AUTH_ERR and not is_api_key:
            if pam_resp['user_info'] is not None:
                # we can try to authenticate via onetime password preserving original
                # pam response if password isn't a known OTP
                uid = pam_resp['user_info']['pw_uid']
                if (resp := await self.middleware.call('auth.onetime_password_authenticate', uid, password)) is not None:
                    resp['user_info'] = pam_resp['user_info']
                    pam_resp = resp

        if pam_resp['code'] == pam.PAM_SUCCESS:
            if is_api_key:
                cred_tag = 'API_KEY'
            elif 'otpw_response' in pam_resp:
                cred_tag = 'OTPW'
            else:
                cred_tag = None

            user_token = await self.authenticate_user(pam_resp['user_info'], cred_tag)
            if user_token is None:
                # Some error occurred when trying to generate our user token
                pam_resp['code'] = pam.PAM_AUTH_ERR
                pam_resp['reason'] = 'Failed to generate user token'

        return {'pam_response': pam_resp, 'user_data': user_token}

    @private
    def onetime_password_authenticate(self, uid, password):
        resp = {'code': pam.PAM_AUTH_ERR, 'reason': 'Authentication failure', 'otpw_response': None}
        otpw_resp = OTPW_MANAGER.authenticate(uid, password)
        match otpw_resp:
            case OTPWResponse.SUCCESS:
                resp = {'code': pam.PAM_SUCCESS, 'reason': '', 'otpw_response': otpw_resp}
            case OTPWResponse.EXPIRED:
                resp = {'code': pam.PAM_CRED_EXPIRED, 'otpw_response': 'Onetime password is expired'}
            case OTPWResponse.NO_KEY:
                # This onetime password doesn't exist. Returning None
                # will fallback to original pam response
                resp = None
            case _:
                resp['otpw_response'] = f'Onetime password authentication failed: {otpw_resp}'

        return resp

    @private
    @pass_app()
    def libpam_authenticate(self, app, username, password, pam_service=MIDDLEWARE_PAM_SERVICE):
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
        if app and app.authentication_context:
            auth_ctx = app.authentication_context
            if auth_ctx.pam_hdl is None:
                auth_ctx.pam_hdl = TrueNAS_PamAuthenticator()
        else:
            # If this is coming through REST API then we may not have app, but
            # this is not an issue since we will not implement PAM converstations
            # over REST.
            auth_ctx = AuthenticationContext()
            auth_ctx.pam_hdl = TrueNAS_PamAuthenticator()

        if pam_service not in PAM_SERVICES:
            self.logger.error('%s: invalid pam service file used for username: %s',
                              pam_service, username)
            raise CallError(f'{pam_service}: invalid pam service file')

        if not os.path.exists(pam_service):
            self.logger.error('PAM service file is missing. Attempting to regenerate')
            self.middleware.call_sync('etc.generate', 'pam_middleware')
            if not os.path.exists(pam_service):
                self.logger.error(
                    '%s: Unable to generate PAM service file for middleware. Denying '
                    'access to user.', username
                )
                return {'code': pam.PAM_ABORT, 'reason': 'Failed to generate PAM service file', 'user_info': None}

        resp = auth_ctx.pam_hdl.authenticate(username, password, service=pam_service)
        return {'code': resp.code, 'reason': resp.reason, 'user_info': resp.user_info}

    @private
    async def authenticate_user(self, user, cred_tag=None):
        """
        Return information for middleware credential based on the specified `user`.

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

        match user['source']:
            case 'LOCAL':
                # Local user
                groups_key = 'local_groups'
                account_flags = ['LOCAL']
            case 'ACTIVEDIRECTORY':
                # Active directory user
                groups_key = 'ds_groups'
                account_flags = ['DIRECTORY_SERVICE', 'ACTIVE_DIRECTORY']
            case 'LDAP':
                # This includes both OpenLDAP and IPA domains
                # Since IPA domains may have cross-realm trusts with separate
                # idmap configuration we will preferentially use the SID if it is
                # available (since it should be static and universally unique)
                groups_key = 'ds_groups'
                account_flags = ['DIRECTORY_SERVICE', 'LDAP']
            case _:
                self.logger.error('[%s]: unknown user source. Rejecting access.', user['source'])
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

        groups = set(user['grouplist'])

        if user_info['twofactor_auth_configured']:
            account_flags.append('2FA')

        if cred_tag:
            account_flags.append(cred_tag)

        if user['pw_uid'] in (0, ADMIN_UID):
            if not user['local']:
                # Although this should be covered in above check for mismatch in
                # value of `local`, perform an extra explicit check for the case
                # of root / root-equivalent accounts.
                self.logger.error(
                    'Rejecting admin account access due to collision with acccount provided '
                    'by a directory service.'
                )
                return None

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
