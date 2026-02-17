from __future__ import annotations
from enum import StrEnum
import os
from time import sleep
from typing import TYPE_CHECKING

from middlewared.api.base.server.app import App
from middlewared.auth import (
    AuthenticationContext, ApiKeySessionManagerCredentials, LoginPasswordSessionManagerCredentials,
    LoginTwofactorSessionManagerCredentials, TokenSessionManagerCredentials,
    LoginOnetimePasswordSessionManagerCredentials, UserSessionManagerCredentials
)
from middlewared.main import Middleware
from middlewared.service import CallError
from middlewared.utils.account.authenticator import (
    ApiKeyPamAuthenticator, TokenPamAuthenticator, UserPamAuthenticator, AccountFlag,
    ScramPamAuthenticator, TrueNASAuthenticatorResponse, TrueNASAuthenticatorStage,
)
from middlewared.utils.account.oath import OATH_FILE
from middlewared.utils.auth import AuthMech, CURRENT_AAL
from truenas_pypam import PAMCode

if TYPE_CHECKING:
    from middlewared.plugins.auth import TokenManager


class CredentialType(StrEnum):
    LOGIN_PASSWORD = 'LOGIN_PASSWORD'
    LOGIN_TWOFACTOR = 'LOGIN_TWOFACTOR'
    ONETIME_PASSWORD = 'ONETIME_PASSWORD'
    API_KEY = 'API_KEY'
    TOKEN = 'TOKEN'
    SCRAM = 'SCRAM'


def _auth_ctx_check(
    middleware: Middleware, *,
    app: App,
    auth_ctx: AuthenticationContext,
    cred_type: CredentialType,
    oath_file_check: bool
) -> bool:
    errmsg = None

    if auth_ctx.pam_hdl is None:
        raise RuntimeError('pam handle was not initialized')

    # Protect against the PAM service file not existing. By default PAM will fallthrough if the
    # service file doesn't exist. We want to try to etc.generate, and if that fails, error out cleanly.
    if not os.path.exists(os.path.join('/etc/pam.d/', auth_ctx.pam_hdl.state.service)):
        middleware.logger.error('PAM service file is missing. Attempting to regenerate')
        middleware.call_sync('etc.generate', 'pam_truenas')
        if not os.path.exists(os.path.join('/etc/pam.d/', auth_ctx.pam_hdl.state.service)):
            errmsg = 'Unable to generate PAM service file for middleware. Denying access.'

    if not errmsg and oath_file_check and not os.path.exists(OATH_FILE):
        # We need to ensure that our OATH file minimally exists because the default in pam configuration
        # is to ignore pam_oath UNKNOWN_USER response.
        middleware.call_sync('etc.generate', 'user')
        if not os.path.exists(OATH_FILE):
            errmsg = 'Unable to generate OATH users file. Denying access.'

    if errmsg:
        middleware.logger.error(errmsg)
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {'credentials': cred_type, 'credentials_data': {}},
            'error': errmsg
        }, False)

    return errmsg is None


def _login_ex_base_args_check(middleware: Middleware, app: App, auth_ctx: AuthenticationContext) -> None:
    if not isinstance(middleware, Middleware):
        raise TypeError(f'{type(middleware)}: expected Middleware type')

    if not isinstance(app, App):
        raise TypeError(f'{type(app)}: expected App type')

    if not isinstance(auth_ctx, AuthenticationContext):
        raise TypeError(f'{type(auth_ctx)}: expected AuthenticationContext type')


def login_ex_password_plain(
    middleware: Middleware,
    *,
    app: App,
    auth_ctx: AuthenticationContext,
    auth_data: dict[str, str],
) -> tuple[
    TrueNASAuthenticatorResponse,
    LoginPasswordSessionManagerCredentials | LoginOnetimePasswordSessionManagerCredentials | None
]:
    """ Handle authentication request with username and password. """
    _login_ex_base_args_check(middleware, app, auth_ctx)

    auth_ctx.pam_hdl = UserPamAuthenticator(username=auth_data['username'], origin=app.origin)
    cred: LoginPasswordSessionManagerCredentials | LoginOnetimePasswordSessionManagerCredentials | None = None
    cred_type = CredentialType.LOGIN_PASSWORD

    if not _auth_ctx_check(middleware, app=app, auth_ctx=auth_ctx, cred_type=cred_type, oath_file_check=True):
        sleep(CURRENT_AAL.get_delay_interval())
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_ABORT,
            reason='Failed authentication configuration precheck'
        )
        return (resp, cred)

    resp = auth_ctx.pam_hdl.authenticate(auth_data['username'], auth_data['password'])
    if resp.code == PAMCode.PAM_SUCCESS and AccountFlag.OTPW in resp.user_info['account_attributes']:
        cred_type = CredentialType.ONETIME_PASSWORD

    if (
        resp.code == PAMCode.PAM_SUCCESS and
        CURRENT_AAL.level.otp_mandatory and
        cred_type != CredentialType.ONETIME_PASSWORD
    ):
        # Plain username / password combo and this is explicitly disallowed by current AAL
        # convert back into an authentication error with a message.
        # Since this succeeded at PAM module level we need to manually insert a fail
        # delay
        sleep(CURRENT_AAL.get_delay_interval())
        # Prevent use of this PAM handle
        auth_ctx.pam_hdl.end()
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_AUTH_ERR,
            reason='User does not have two factor authentication enabled.'
        )

    if resp.code == PAMCode.PAM_SUCCESS:
        # auditing success is handled by session manager login function
        user_info = middleware.call_sync('auth.authenticate_user', resp.user_info)
        if user_info:
            if cred_type == CredentialType.ONETIME_PASSWORD:
                cred = LoginOnetimePasswordSessionManagerCredentials(
                    user_info,
                    CURRENT_AAL.level,
                    auth_ctx.pam_hdl
                )
            else:
                cred = LoginPasswordSessionManagerCredentials(
                    user_info,
                    CURRENT_AAL.level,
                    auth_ctx.pam_hdl
                )
        else:
            auth_ctx.pam_hdl.end()
            resp = TrueNASAuthenticatorResponse(
                stage=TrueNASAuthenticatorStage.AUTH,
                code=PAMCode.PAM_PERM_DENIED,
                reason='User lacks API access.'
            )
            middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
                'credentials': {
                    'credentials': cred_type.value,
                    'credentials_data': {'username': auth_data['username']},
                },
                'error': resp.reason
            }, False)

    elif resp.code == PAMCode.PAM_CONV_AGAIN:
        # We have prompt from PAM stack to provide OATH token
        # set hint for next mechanism and current in-progress user
        auth_ctx.next_mech = AuthMech.OTP_TOKEN
        auth_ctx.auth_data = {'user': {'username': auth_data['username']}}

    else:
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {
                'credentials': cred_type.value,
                'credentials_data': {'username': auth_data['username']},
             },
            'error': resp.reason
        }, False)

    return (resp, cred)


def login_ex_api_key_plain(
    middleware: Middleware,
    *,
    app: App,
    auth_ctx: AuthenticationContext,
    auth_data: dict[str, str],
) -> tuple[TrueNASAuthenticatorResponse, ApiKeySessionManagerCredentials | None]:
    """ Handle authentication request with raw API key. """
    _login_ex_base_args_check(middleware, app, auth_ctx)
    auth_ctx.pam_hdl = ApiKeyPamAuthenticator(username=auth_data['username'], origin=app.origin)
    cred = None
    cred_type = CredentialType.API_KEY

    # API keys never have OATH plumbing
    if not _auth_ctx_check(middleware, app=app, auth_ctx=auth_ctx, cred_type=cred_type, oath_file_check=False):
        sleep(CURRENT_AAL.get_delay_interval())
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_ABORT,
            reason='Failed authentication configuration precheck'
        )
        return (resp, cred)

    resp = auth_ctx.pam_hdl.authenticate(auth_data['username'], auth_data['api_key'])

    # We need the key info so that we can generate a useful
    # audit entry in case of failure.
    try:
        key_id = int(auth_data['api_key'].split('-')[0])
        key = middleware.call_sync(
            'api_key.query', [['id', '=', key_id]],
            {'get': True, 'select': ['id', 'name', 'expires_at', 'revoked']}
        )
    except Exception:
        key = None

    if key and resp.code == PAMCode.PAM_AUTHINFO_UNAVAIL:
        # Key may be expired or revoked. In both of these cases we won't
        # have a key in the user's keyring. There's no way to differentiate
        # at PAM level because both fail with ENOKEY.
        if key['expires_at']:
            resp = TrueNASAuthenticatorResponse(
                stage=TrueNASAuthenticatorStage.AUTH,
                code=PAMCode.PAM_CRED_EXPIRED,
                reason='Api key is expired'
            )

        elif key['revoked']:
            resp = TrueNASAuthenticatorResponse(
                stage=TrueNASAuthenticatorStage.AUTH,
                code=PAMCode.PAM_CRED_EXPIRED,
                reason='API key is revoked'
            )

        else:
            middleware.logger.warning('%s: unexpected PAM_AUTHINFO_UNAVAIL response '
                                      'for API key. Forcibly regenerating API keys.',
                                      key['name'])
            middleware.call_sync('etc.generate', 'pam_truenas')

    if resp.code == PAMCode.PAM_SUCCESS:
        if not app.origin.secure_transport:
            # Per NEP if plain API key auth occurs over insecure transport
            # the key should be automatically revoked.
            middleware.call_sync('api_key.revoke', key_id, 'Attempt to use over an insecure transport')
            sleep(CURRENT_AAL.get_delay_interval())

            resp = TrueNASAuthenticatorResponse(
                stage=TrueNASAuthenticatorStage.AUTH,
                code=PAMCode.PAM_CRED_EXPIRED,
                reason='API key revoked due to insecure transport'
            )
            auth_ctx.pam_hdl.end()
        else:
            # Now perform API access check
            user_info = middleware.call_sync('auth.authenticate_user', resp.user_info)
            if user_info:
                cred = ApiKeySessionManagerCredentials(user_info, key, CURRENT_AAL.level, auth_ctx.pam_hdl)
            else:
                auth_ctx.pam_hdl.end()
                resp = TrueNASAuthenticatorResponse(
                    stage=TrueNASAuthenticatorStage.AUTH,
                    code=PAMCode.PAM_PERM_DENIED,
                    reason='User lacks API access.'
                )

    if resp.code != PAMCode.PAM_SUCCESS:
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {
                'credentials': 'API_KEY',
                'credentials_data': {'username': auth_data['username'], 'api_key': key if key else '<INVALID>'}
            },
            'error': resp.reason,
        }, False)

    return (resp, cred)


def login_ex_oath_token(
    middleware: Middleware,
    *,
    app: App,
    auth_ctx: AuthenticationContext,
    auth_data: dict[str, str],
) -> tuple[TrueNASAuthenticatorResponse, LoginTwofactorSessionManagerCredentials | None]:
    """ Handle continuation of auth with OATH token. """
    _login_ex_base_args_check(middleware, app, auth_ctx)
    cred = None
    cred_type = CredentialType.LOGIN_TWOFACTOR

    # OATH token authentication requires OATH file
    if not _auth_ctx_check(middleware, app=app, auth_ctx=auth_ctx, cred_type=cred_type, oath_file_check=True):
        sleep(CURRENT_AAL.get_delay_interval())
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_ABORT,
            reason='Failed authentication configuration precheck'
        )
        return (resp, cred)

    if not isinstance(auth_ctx.pam_hdl, UserPamAuthenticator):
        raise RuntimeError('Expected UserPamAuthenticator for OATH token authentication')

    resp = auth_ctx.pam_hdl.authenticate_oath(auth_data['otp_token'])
    data = auth_ctx.auth_data
    auth_ctx.auth_data = None
    auth_ctx.next_mech = None

    if data is None:
        raise CallError('No authentication context data available for OTP validation')

    if resp.code == PAMCode.PAM_SUCCESS:
        user_info = middleware.call_sync('auth.authenticate_user', resp.user_info)
        if user_info:
            cred = LoginTwofactorSessionManagerCredentials(
                user_info, CURRENT_AAL.level, auth_ctx.pam_hdl
            )
        else:
            sleep(CURRENT_AAL.get_delay_interval())
            resp = TrueNASAuthenticatorResponse(
                stage=TrueNASAuthenticatorStage.AUTH,
                code=PAMCode.PAM_PERM_DENIED,
                reason='User lacks API access.'
            )
            auth_ctx.pam_hdl.end()
            middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
                'credentials': {
                    'credentials': 'LOGIN_TWOFACTOR',
                    'credentials_data': {'username': data['user']['username']},
                },
                'error': 'User lacks API access.'
            }, False)

    else:
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {
                'credentials': 'LOGIN_TWOFACTOR',
                'credentials_data': {'username': data['user']['username']},
            },
            'error': f'One-time token validation failed: {resp.reason}'
        }, False)

    return (resp, cred)


def login_ex_token_plain(
    middleware: Middleware,
    *,
    app: App,
    auth_ctx: AuthenticationContext,
    token_manager: TokenManager,
    auth_data: dict[str, str],
) -> tuple[TrueNASAuthenticatorResponse, TokenSessionManagerCredentials | None]:
    """ Handle authentication with legacy auth tokens. This need to be replaced
    in the future with a more secure method. """
    _login_ex_base_args_check(middleware, app, auth_ctx)

    cred = None
    cred_type = CredentialType.TOKEN

    # Tokens don't use OATH plumbing
    token_str = auth_data['token']
    token = token_manager.get(token_str, app.origin)
    if token is None:
        sleep(CURRENT_AAL.get_delay_interval())
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {
                'credentials': cred_type.value,
                'credentials_data': {'token': token_str}
            },
            'error': 'Invalid token',
        }, False)
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_AUTH_ERR,
            reason='Invalid token'
        )
        return (resp, cred)

    elif token.attributes:
        sleep(CURRENT_AAL.get_delay_interval())
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {
                'credentials': cred_type.value,
                'credentials_data': {'token': token_str}
            },
            'error': 'Bad token',
        }, False)
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_AUTH_ERR,
            reason='Bad token'
        )
        return (resp, cred)

    # Use the AF_UNIX style authenticator with username from base auth
    root_cred = token.root_credentials()
    if root_cred is None:
        raise CallError('Token has no root credentials - this indicates a serious system error')

    if root_cred.is_user_session:
        username = root_cred.dump()['username']
    else:
        username = 'root'

    auth_ctx.pam_hdl = TokenPamAuthenticator(username=username, origin=app.origin)
    cred = TokenSessionManagerCredentials(token_manager, token, auth_ctx.pam_hdl)
    pam_resp = cred.pam_authenticate()
    if pam_resp.code != PAMCode.PAM_SUCCESS:
        # Account may have gotten locked between when token originally generated and when it was used.
        # Alternatively we may have hit session limits.
        sleep(CURRENT_AAL.get_delay_interval())

        # Unlike other failure types we can't print the token in the audit log
        # since it is actually still valid
        middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
            'credentials': {'credentials': cred_type.value, 'credentials_data': cred.dump()},
            'error': pam_resp.reason,
        }, False)

    return (pam_resp, cred)


def login_ex_scram(
    middleware: Middleware,
    *,
    app: App,
    auth_ctx: AuthenticationContext,
    auth_data: dict[str, str],
) -> tuple[TrueNASAuthenticatorResponse, ApiKeySessionManagerCredentials | UserSessionManagerCredentials | None]:
    """ Handle authentication request with SCRAM authentication. """
    _login_ex_base_args_check(middleware, app, auth_ctx)
    cred: ApiKeySessionManagerCredentials | UserSessionManagerCredentials | None = None
    cred_type = CredentialType.SCRAM

    # SCRAM authentication never has OATH plumbing
    if not _auth_ctx_check(middleware, app=app, auth_ctx=auth_ctx, cred_type=cred_type, oath_file_check=False):
        sleep(CURRENT_AAL.get_delay_interval())
        resp = TrueNASAuthenticatorResponse(
            stage=TrueNASAuthenticatorStage.AUTH,
            code=PAMCode.PAM_ABORT,
            reason='Failed authentication configuration precheck'
        )
        return (resp, cred)

    match auth_data['scram_type']:
        case 'CLIENT_FIRST_MESSAGE':
            auth_ctx.pam_hdl = ScramPamAuthenticator(
                client_first_message=auth_data['rfc_str'], origin=app.origin
            )

            resp = auth_ctx.pam_hdl.handle_first_message()
            if resp.code == PAMCode.PAM_CONV_AGAIN:
                auth_ctx.next_mech = AuthMech.SCRAM

            else:
                middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
                   'credentials': {'credentials': 'SCRAM', 'credentials_data': {}},
                   'error': resp.reason,
                }, False)

        case 'CLIENT_FINAL_MESSAGE':
            if auth_ctx.next_mech != AuthMech.SCRAM:
                raise CallError('SCRAM authentication is not in progress')

            if not isinstance(auth_ctx.pam_hdl, ScramPamAuthenticator):
                raise RuntimeError('Expected ScramPamAuthenticator for SCRAM final message')

            auth_ctx.next_mech = None

            resp = auth_ctx.pam_hdl.handle_final_message(auth_data['rfc_str'])
            if resp.code == PAMCode.PAM_SUCCESS:
                # SCRAM authentication can in theory be either an API key or password
                user_info = middleware.call_sync('auth.authenticate_user', resp.user_info)
                if auth_ctx.pam_hdl.dbid:
                    key = middleware.call_sync(
                        'api_key.query', [['id', '=', auth_ctx.pam_hdl.dbid]],
                        {'get': True, 'select': ['id', 'name']}
                    )
                    cred = ApiKeySessionManagerCredentials(
                        user_info, key, CURRENT_AAL.level, auth_ctx.pam_hdl
                    )
                else:
                    cred = UserSessionManagerCredentials(
                        user_info, CURRENT_AAL.level, auth_ctx.pam_hdl
                    )
            else:
                middleware.log_audit_message_sync(app, 'AUTHENTICATION', {
                    'credentials': {'credentials': 'SCRAM', 'credentials_data': {}},
                    'error': resp.reason,
                }, False)

        case _:
            middleware.logger.error('%s: invalid scram message type', auth_data['scram_type'])
            raise CallError(f'{auth_data["scram_type"]}: invalid SCRAM type')

    return (resp, cred)
