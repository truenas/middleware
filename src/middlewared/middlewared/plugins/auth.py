import asyncio
import random
from datetime import timedelta
import errno
import pam
import time

from middlewared.api import api_method
from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketAppEvent
from middlewared.api.current import (
    AuthLegacyPasswordLoginArgs, AuthLegacyApiKeyLoginArgs, AuthLegacyTokenLoginArgs,
    AuthLegacyTwoFactorArgs, AuthLegacyResult,
    AuthLoginExArgs, AuthLoginExContinueArgs, AuthLoginExResult,
    AuthMeArgs, AuthMeResult,
    AuthMechChoicesArgs, AuthMechChoicesResult,
    AuthSessionEntry,
    AuthGenerateTokenArgs, AuthGenerateTokenResult,
    AuthSessionLogoutArgs, AuthSessionLogoutResult,
    AuthSetAttributeArgs, AuthSetAttributeResult,
    AuthTerminateSessionArgs, AuthTerminateSessionResult,
    AuthTerminateOtherSessionsArgs, AuthTerminateOtherSessionsResult,
)
from middlewared.auth import (UserSessionManagerCredentials, UnixSocketSessionManagerCredentials,
                              ApiKeySessionManagerCredentials, LoginPasswordSessionManagerCredentials,
                              LoginTwofactorSessionManagerCredentials, AuthenticationContext,
                              TruenasNodeSessionManagerCredentials, TokenSessionManagerCredentials,
                              dump_credentials)
from middlewared.plugins.account_.constants import MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE
from middlewared.service import (
    Service, filterable_api_method, filter_list,
    pass_app, private, cli_private, CallError,
)
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.auth import (
    aal_auth_mechanism_check, AuthMech, AuthResp, AuthenticatorAssuranceLevel, AA_LEVEL1,
    AA_LEVEL2, AA_LEVEL3, CURRENT_AAL, MAX_OTP_ATTEMPTS,
)
from middlewared.utils.crypto import generate_token
from middlewared.utils.time_utils import utc_now

PAM_SERVICES = {MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE}


class TokenManager:
    def __init__(self):
        self.tokens = {}

    def create(self, ttl, attributes, match_origin, parent_credentials, session_id):
        credentials = parent_credentials
        if isinstance(credentials, TokenSessionManagerCredentials):
            if root_credentials := credentials.token.root_credentials():
                credentials = root_credentials

        token = generate_token(48, url_safe=True)
        self.tokens[token] = Token(self, token, ttl, attributes, match_origin, credentials, session_id)
        return self.tokens[token]

    def get(self, token, origin):
        token = self.tokens.get(token)
        if token is None:
            return None

        if not token.is_valid():
            self.tokens.pop(token.token)
            return None

        if token.match_origin:
            if not isinstance(origin, type(token.match_origin)):
                return None
            if not token.match_origin.match(origin):
                return None

        return token

    def destroy(self, token):
        self.tokens.pop(token.token, None)

    def destroy_by_session_id(self, session_id):
        self.tokens = {k: v for k, v in self.tokens.items() if session_id not in v.session_ids}


class Token:
    def __init__(self, manager, token, ttl, attributes, match_origin, parent_credentials, session_id):
        self.manager = manager
        self.token = token
        self.ttl = ttl
        self.attributes = attributes
        self.match_origin = match_origin
        self.parent_credentials = parent_credentials
        self.session_ids = {session_id}

        self.last_used_at = time.monotonic()

    def is_valid(self):
        return time.monotonic() < self.last_used_at + self.ttl

    def notify_used(self):
        self.last_used_at = time.monotonic()

    def root_credentials(self):
        credentials = self.parent_credentials
        while True:
            if isinstance(credentials, TokenSessionManagerCredentials):
                credentials = credentials.token.parent_credentials
            elif credentials is None:
                return None
            else:
                return credentials


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.middleware = None

    async def login(self, app, credentials):
        if app.authenticated:
            self.sessions[app.session_id].credentials = credentials
            app.authenticated_credentials = credentials
            return

        session = Session(self, credentials, app)
        self.sessions[app.session_id] = session

        app.authenticated = True
        app.authenticated_credentials = credentials

        app.register_callback(RpcWebSocketAppEvent.MESSAGE, self._app_on_message)
        app.register_callback(RpcWebSocketAppEvent.CLOSE, self._app_on_close)

        if not is_internal_session(session):
            self.middleware.send_event("auth.sessions", "ADDED", fields=dict(id=app.session_id, **session.dump()))
            await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                "credentials": dump_credentials(credentials),
                "error": None,
            }, True)

    async def logout(self, app):
        session = self.sessions.pop(app.session_id, None)

        if session is not None:
            session.credentials.logout()

            if not is_internal_session(session):
                self.middleware.send_event("auth.sessions", "REMOVED", fields=dict(id=app.session_id))

        app.authenticated = False

    async def _app_on_message(self, app, message):
        session = self.sessions.get(app.session_id)
        if session is None:
            app.authenticated = False
            return

        if not session.credentials.is_valid():
            await self.logout(app)
            return

        session.credentials.notify_used()

    async def _app_on_close(self, app):
        await self.logout(app)


class Session:
    def __init__(self, manager, credentials, app):
        self.manager = manager
        self.credentials = credentials
        self.app = app

        self.created_at = time.monotonic()

    def dump(self):
        return {
            "origin": str(self.app.origin),
            **dump_credentials(self.credentials),
            "created_at": utc_now() - timedelta(seconds=time.monotonic() - self.created_at),
        }


def is_internal_session(session) -> bool:
    try:
        is_root_sock = session.app.origin.is_unix_family and session.app.origin.uid == 0
        if is_root_sock:
            return True
    except AttributeError:
        # session.app.origin can be NoneType
        pass

    if isinstance(session.app.authenticated_credentials, TruenasNodeSessionManagerCredentials):
        return True

    return False


class UserWebUIAttributeModel(sa.Model):
    __tablename__ = 'account_bsdusers_webui_attribute'

    id = sa.Column(sa.Integer(), primary_key=True)
    uid = sa.Column(sa.Integer(), unique=True)
    attributes = sa.Column(sa.JSON())


class AuthService(Service):

    class Config:
        cli_namespace = "auth"

    session_manager = SessionManager()

    token_manager = TokenManager()

    def __init__(self, *args, **kwargs):
        super(AuthService, self).__init__(*args, **kwargs)
        self.session_manager.middleware = self.middleware

    @filterable_api_method(item=AuthSessionEntry, private=False, roles=['AUTH_SESSIONS_READ'])
    @pass_app()
    def sessions(self, app, filters, options):
        """
        Returns list of active auth sessions.

        Example of return value:

        [
            {
                "id": "NyhB1J5vjPjIV82yZ6caU12HLA1boDJcZNWuVQM4hQWuiyUWMGZTz2ElDp7Yk87d",
                "origin": "192.168.0.3:40392",
                "credentials": "LOGIN_PASSWORD",
                "credentials_data": {"username": "root"},
                "current": True,
                "internal": False,
                "created_at": {"$date": 1545842426070}
            }
        ]

        `credentials` can be `UNIX_SOCKET`, `ROOT_TCP_SOCKET`, `LOGIN_PASSWORD`, `API_KEY` or `TOKEN`,
        depending on what authentication method was used.
        For `UNIX_SOCKET` and `LOGIN_PASSWORD` logged-in `username` field will be provided in `credentials_data`.
        For `API_KEY` corresponding `api_key` will be provided in `credentials_data`.
        For `TOKEN` its `parent` credential will be provided in `credentials_data`.

        If you want to exclude all internal connections from the list, call this method with following arguments:

        [
            [
                ["internal", "=", True]
            ]
        ]
        """
        return filter_list(
            [
                dict(
                    id=session_id,
                    current=app.session_id == session_id,
                    internal=is_internal_session(session),
                    **session.dump()
                )
                for session_id, session in sorted(self.session_manager.sessions.items(),
                                                  key=lambda t: t[1].created_at)
            ],
            filters,
            options,
        )

    @api_method(AuthTerminateSessionArgs, AuthTerminateSessionResult, roles=['AUTH_SESSIONS_WRITE'])
    async def terminate_session(self, id_):
        """
        Terminates session `id`.
        """
        session = self.session_manager.sessions.get(id_)
        if session is None:
            return False

        self.token_manager.destroy_by_session_id(id_)

        await session.app.ws.close()
        return True

    @api_method(AuthTerminateOtherSessionsArgs, AuthTerminateOtherSessionsResult, roles=['AUTH_SESSIONS_WRITE'])
    @pass_app()
    async def terminate_other_sessions(self, app):
        """
        Terminates all other sessions (except the current one).
        """
        errors = []
        for session_id, session in list(self.session_manager.sessions.items()):
            if session_id == app.session_id:
                continue

            if is_internal_session(session):
                continue

            try:
                await self.terminate_session(session_id)
            except Exception as e:
                errors.append(str(e))

        if errors:
            raise CallError("\n".join(["Unable to terminate all sessions:"] + errors))

        return True

    @api_method(AuthGenerateTokenArgs, AuthGenerateTokenResult, authorization_required=False)
    @pass_app(rest=True)
    def generate_token(self, app, ttl, attrs, match_origin):
        """
        Generate a token to be used for authentication.

        `ttl` stands for Time To Live, in seconds. The token will be invalidated if the connection
        has been inactive for a time greater than this.

        `attrs` is a general purpose object/dictionary to hold information about the token.

        `match_origin` will only allow using this token from the same IP address or with the same user UID.
        """
        if ttl is None:
            ttl = 600

        token = self.token_manager.create(
            ttl,
            attrs,
            app.origin if match_origin else None,
            app.authenticated_credentials,
            app.session_id,
        )

        return token.token

    @private
    def get_token(self, token_id):
        try:
            return {
                'attributes': self.token_manager.tokens[token_id].attributes,
            }
        except KeyError:
            return None

    @private
    def get_token_for_action(self, token_id, origin, method, resource):
        if (token := self.token_manager.get(token_id, origin)) is None:
            return None

        if token.attributes:
            return None

        if not token.parent_credentials.authorize(method, resource):
            return None

        return TokenSessionManagerCredentials(self.token_manager, token)

    @private
    def get_token_for_shell_application(self, token_id, origin):
        if (token := self.token_manager.get(token_id, origin)) is None:
            return None

        if token.attributes:
            return None

        root_credentials = token.root_credentials()
        if not isinstance(root_credentials, UserSessionManagerCredentials):
            return None

        if not root_credentials.user['privilege']['web_shell']:
            return None

        return {
            'username': root_credentials.user['username'],
        }

    @api_method(AuthLegacyTwoFactorArgs, AuthLegacyResult, authentication_required=False)
    async def two_factor_auth(self, username, password):
        """
        Returns true if two-factor authorization is required for authorizing user's login.
        """
        user_authenticated = await self.middleware.call('auth.authenticate_plain', username, password)
        return user_authenticated and (
            await self.middleware.call('auth.twofactor.config')
        )['enabled'] and '2FA' in user_authenticated['account_attributes']

    @cli_private
    @api_method(AuthLegacyPasswordLoginArgs, AuthLegacyResult, authentication_required=False)
    @pass_app()
    async def login(self, app, username, password, otp_token):
        """
        Authenticate session using username and password.
        `otp_token` must be specified if two factor authentication is enabled.
        """

        resp = await self.login_ex(app, {
            'mechanism': AuthMech.PASSWORD_PLAIN,
            'username': username,
            'password': password,
            'login_options': {'user_info': False},
        })

        match resp['response_type']:
            case AuthResp.SUCCESS:
                return True
            case AuthResp.OTP_REQUIRED:
                if otp_token is None:
                    return False

                otp_resp = await self.login_ex(app, {
                    'mechanism': AuthMech.OTP_TOKEN.name,
                    'otp_token': otp_token
                })
                return otp_resp['response_type'] == AuthResp.SUCCESS
            case _:
                return False

    @private
    async def set_authenticator_assurance_level(self, level: str):
        """
        This method is for CI tests. Currently we only support AA_LEVEL_1.

        See NIST SP 800-63B Section 4:
        https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-63b.pdf
        """
        self.logger.warning('Setting AAL to %s', level)
        match level:
            case 'LEVEL_1':
                level = AA_LEVEL1
            case 'LEVEL_2':
                level = AA_LEVEL2
            case 'LEVEL_3':
                level = AA_LEVEL3
            case _:
                raise CallError(f'{level}: unknown authenticator assurance level')

        CURRENT_AAL.level = level

    @private
    async def check_auth_mechanism(
        self,
        app,
        mechanism: AuthMech,
        auth_ctx: AuthenticationContext,
        level: AuthenticatorAssuranceLevel
    ) -> None:

        # The current session may be in the middle of a challenge-response conversation
        # and so we need to validate that what we received from client was expected
        # next message.
        if auth_ctx.next_mech and mechanism is not auth_ctx.next_mech:
            expected = auth_ctx.auth_data['user']['username']
            self.logger.debug('%s: received auth mechanism for user %s while expecting next auth mechanism: %s',
                              mechanism, expected, auth_ctx.next_mech)

            expected = auth_ctx.auth_data['user']['username']
            if auth_ctx.next_mech is AuthMech.OTP_TOKEN:
                errmsg = (
                    'Abandoning login attempt after being presented wtih '
                    'requirement for second factor for authentication.'
                )

                await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                    'credentials': {
                        'credentials': 'LOGIN_TWOFACTOR',
                        'credentials_data': {
                            'username': expected,
                        },
                    },
                    'error': errmsg
                }, False)

            # Discard in-progress auth attempt
            auth_ctx.next_mech = None
            auth_ctx.auth_data = None

        # OTP tokens are only permitted when prompted
        if auth_ctx.next_mech is None and mechanism == AuthMech.OTP_TOKEN.name:
            raise CallError(f'{mechanism}: no authentication in progress', errno.EINVAL)

        # Verify that auth mechanism is permitted under authenticator assurance level
        if not aal_auth_mechanism_check(mechanism, level):
            # Per NIST SP 800-63B only permitted authenticator types may be used
            raise CallError(
                f'{mechanism}: mechanism is not supported at current authenticator level.',
                errno.EOPNOTSUPP
            )

    @api_method(AuthMechChoicesArgs, AuthMechChoicesResult, authentication_required=False)
    async def mechanism_choices(self) -> list:
        """ Get list of available authentication mechanisms available for auth.login_ex """
        aal = CURRENT_AAL.level
        return [mech.name for mech in aal.mechanisms]

    @cli_private
    @api_method(AuthLoginExContinueArgs, AuthLoginExResult, authentication_required=False)
    @pass_app()
    async def login_ex_continue(self, app, data):
        """
        Continue in-progress authentication attempt. This endpoint should be
        called to continue an auth.login_ex attempt that returned OTP_REQUIRED.

        This is a convenience wrapper around auth.login_ex for API consumers.

        params:
            mechanism: the mechanism by which to continue authentication.
            Currently the only supported mechanism here is OTP_TOKEN.

            OTP_TOKEN
            otp_token: one-time password token. This is only permitted if
            a previous auth.login_ex call responded with "OTP_REQUIRED".

        returns:
            JSON object containing the following keys:

            `response_type` - will be one of the following:
            SUCCESS - continued auth was required

            OTP_REQUIRED - otp token was rejected. API consumer may call this
            endpoint again with correct OTP token.

            AUTH_ERR - invalid OTP token submitted too many times.
        """
        return await self.login_ex(app, data)

    @cli_private
    @api_method(AuthLoginExArgs, AuthLoginExResult, authentication_required=False)
    @pass_app()
    async def login_ex(self, app, data):
        """
        Authenticate using one of a variety of mechanisms

        NOTE: mechanisms with a _PLAIN suffix indicate that they involve
        passing plain-text passwords or password-equivalent strings and
        should not be used on untrusted / insecure transport. Available
        mechanisms will be expanded in future releases.

        params:
            This takes a single argument consistning of a JSON object with the
            following keys:

            mechanism: the mechanism by which to authenticate to the backend
            the exact parameters to use vary by mechanism and are described
            below

            PASSWORD_PLAIN
            username: username with which to authenticate
            password: password with which to authenticate
            login_options: dictionary with additional authentication options

            API_KEY_PLAIN
            username: username with which to authenticate
            api_key: API key string
            login_options: dictionary with additional authentication options

            AUTH_TOKEN_PLAIN
            token: authentication token string
            login_options: dictionary with additional authentication options

            OTP_TOKEN
            otp_token: one-time password token. This is only permitted if
            a previous auth.login_ex call responded with "OTP_REQUIRED".

            login_options
            user_info: boolean - include auth.me output in successful responses.

        raises:
            CallError: a middleware CallError may be raised in the following
                circumstances.

            * An multistep challenge-response authentication mechanism is being
              used and the specified `mechanism` does not match the expected
              next step for authentication. In this case the errno will be set
              to EBUSY.

            * OTP_TOKEN mechanism was passed without an explicit request from
              a previous authentication step. In this case the errno will be set
              to EINVAL.

            * Current authenticator assurance level prohibits the use of the
              specified authentication mechanism. In this case the errno will be
              set to EOPNOTSUPP.

        returns:
            JSON object containing the following keys:

            response_type: string indicating the results of the current authentication
                mechanism. This is used to inform client of nature of authentication
                error or whether further action will be required in order to complete
                authentication.

            <additional keys per response_type>

        Notes about response types:

        SUCCESS:
        additional key:
            user_info: includes auth.me output for the resulting authenticated
            credentials.

        OTP_REQUIRED
        additional key:
            username: normalized username of user who must provide an OTP token.

        AUTH_ERR
        Generic authentication error corresponds to PAM_AUTH_ERR and PAM_USER_UNKOWN
        from libpam. This may be returned if the account does not exist or if the
        credential is incorrect.

        EXPIRED
        The specified credential is expired and not suitable for authentication.
        """
        mechanism = AuthMech[data['mechanism']]
        auth_ctx = app.authentication_context
        login_fn = self.session_manager.login
        response = {'response_type': AuthResp.AUTH_ERR}

        await self.check_auth_mechanism(app, mechanism, auth_ctx, CURRENT_AAL.level)

        match mechanism:
            case AuthMech.PASSWORD_PLAIN:
                # Both of these mechanisms are de-factor username + password
                # combinations and pass through libpam.
                resp = await self.get_login_user(
                    app,
                    data['username'],
                    data['password'],
                    mechanism
                )
                if resp['otp_required']:
                    # A one-time password is required for this user account and so
                    # we should request it from API client.
                    auth_ctx.next_mech = AuthMech.OTP_TOKEN
                    auth_ctx.auth_data = {'cnt': 0, 'user': resp['user_data']}
                    return {
                        'response_type': AuthResp.OTP_REQUIRED,
                        'username': resp['user_data']['username']
                    }
                elif CURRENT_AAL.level.otp_mandatory:
                    if resp['pam_response'] == 'SUCCESS':
                        # Insert a failure delay so that we don't leak information about
                        # the PAM response
                        await asyncio.sleep(random.uniform(1, 2))
                    raise CallError(
                        'Two-factor authentication is requried at the current authenticator level.',
                        errno.EOPNOTSUPP
                    )

                match resp['pam_response']['code']:
                    case pam.PAM_SUCCESS:
                        cred = LoginPasswordSessionManagerCredentials(resp['user_data'], CURRENT_AAL.level)
                        await login_fn(app, cred)
                    case pam.PAM_AUTH_ERR:
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': 'LOGIN_PASSWORD',
                                'credentials_data': {'username': data['username']},
                            },
                            'error': 'Bad username or password'
                        }, False)
                    case _:
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': 'LOGIN_PASSWORD',
                                'credentials_data': {'username': data['username']},
                            },
                            'error': resp['pam_response']['reason']
                        }, False)

            case AuthMech.API_KEY_PLAIN:
                # API key that we receive over wire is concatenation of the
                # datastore `id` of the particular key with the key itself,
                # delimited by a dash. <id>-<key>.
                resp = await self.get_login_user(
                    app,
                    data['username'],
                    data['api_key'],
                    mechanism
                )
                if resp['pam_response']['code'] == pam.PAM_AUTHINFO_UNAVAIL:
                    # This is a special error code that means we need to
                    # etc.generate because we somehow got garbage in the file.
                    # It should not happen, but we must try to recover.

                    self.logger.warning('API key backend has errors that require regenerating its file.')
                    await self.middleware.call('etc.generate', 'pam_middleware')

                    # We've exhausted steps we can take, so we'll take the
                    # response to second request as authoritative
                    resp = await self.get_login_user(
                        app,
                        data['username'],
                        data['api_key'],
                        mechanism
                    )

                # Retrieve the API key here so that we can upgrade the underlying
                # hash type and iterations if needed (since we have plain-text).
                # We also need the key info so that we can generate a useful
                # audit entry in case of failure.
                try:
                    key_id = int(data['api_key'].split('-')[0])
                    key = await self.middleware.call(
                        'api_key.query', [['id', '=', key_id]],
                        {'get': True, 'select': ['id', 'name', 'keyhash', 'expired']}
                    )
                    thehash = key.pop('keyhash')
                except Exception:
                    key = None

                if resp['pam_response']['code'] == pam.PAM_CRED_EXPIRED:
                    # Give more precise reason for login failure for audit trails
                    # because we need to differentiate between key and account
                    # being expired.
                    resp['pam_response']['reason'] = 'Api key is expired.'

                if resp['pam_response']['code'] == pam.PAM_SUCCESS:
                    if thehash.startswith('$pbkdf2-sha256'):
                        # Legacy API key with insufficient iterations. Since we
                        # know that the plain-text we have here is correct, we can
                        # use it to update the hash in backend.
                        await self.middleware.call('api_key.update_hash', data['api_key'])

                    cred = ApiKeySessionManagerCredentials(resp['user_data'], key, CURRENT_AAL.level)
                    await login_fn(app, cred)
                else:
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'API_KEY',
                            'credentials_data': {
                                'username': data['username'],
                                'api_key': key,
                            }
                        },
                        'error': resp['pam_response']['reason'],
                    }, False)

            case AuthMech.OTP_TOKEN:
                # We've received a one-time password token based in response to our
                # response to an earlier authentication attempt. This means our auth
                # context has user information. We don't re-request username from the
                # client as this would open possibility of user trivially bypassing
                # 2FA.
                otp_ok = await self.middleware.call(
                    'user.verify_twofactor_token',
                    auth_ctx.auth_data['user']['username'],
                    data['otp_token'],
                )
                resp = {
                    'pam_response': {
                        'code': pam.PAM_SUCCESS if otp_ok else pam.PAM_AUTH_ERR,
                        'reason': None
                    }
                }
                # get reference to auth data
                auth_data = auth_ctx.auth_data

                # reset the auth_ctx state
                auth_ctx.next_mech = None
                auth_ctx.auth_data = None

                if otp_ok:
                    # Per feedback to NEP-053 it was decided to only request second
                    # factor for password-based logins (not user-linked API keys).
                    # Hence we don't have to worry about whether this is based on
                    # an API key.
                    cred = LoginTwofactorSessionManagerCredentials(auth_data['user'], CURRENT_AAL.level)
                    await login_fn(app, cred)
                else:
                    # Add a sleep like pam_delay() would add for pam_oath
                    await asyncio.sleep(random.uniform(1, 2))
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'LOGIN_TWOFACTOR',
                            'credentials_data': {
                                'username': auth_data['user']['username'],
                            },
                        },
                        'error': 'One-time token validation failed.'
                    }, False)

                    # Give the user a few attempts to recover a fat-fingered OTP cred
                    if auth_data['cnt'] < MAX_OTP_ATTEMPTS:
                        auth_data['cnt'] += 1
                        auth_ctx.auth_data = auth_data
                        auth_ctx.next_mech = AuthMech.OTP_TOKEN

                        return {
                            'response_type': AuthResp.OTP_REQUIRED,
                            'username': auth_data['user']['username']
                        }

            case AuthMech.TOKEN_PLAIN:
                # We've received a authentication token that _should_ have been
                # generated by `auth.generate_token`. For consistency with other
                # authentication methods a failure delay has been added, but this
                # may be removed more safely than for other authentication methods
                # since the tokens are short-lived.
                token_str = data['token']
                token = self.token_manager.get(token_str, app.origin)
                if token is None:
                    await asyncio.sleep(random.uniform(1, 2))
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'TOKEN',
                            'credentials_data': {
                                'token': token_str,
                            }
                        },
                        'error': 'Invalid token',
                    }, False)
                    return response

                if token.attributes:
                    await asyncio.sleep(random.uniform(1, 2))
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'TOKEN',
                            'credentials_data': {
                                'token': token.token,
                            }
                        },
                        'error': 'Bad token',
                    }, False)
                    return response

                cred = TokenSessionManagerCredentials(self.token_manager, token)
                await login_fn(app, cred)
                resp = {
                    'pam_response': {
                        'code': pam.PAM_SUCCESS,
                        'reason': None
                    }
                }

            case _:
                # This shouldn't happen so we'll log it and raise a call error
                self.logger.error('%s: unexpected authentication mechanism', mechanism)
                raise CallError(f'{mechanism}: unexpected authentication mechanism')

        match resp['pam_response']['code']:
            case pam.PAM_SUCCESS:
                response['response_type'] = AuthResp.SUCCESS
                if data['login_options']['user_info']:
                    response['user_info'] = await self.me(app)
                else:
                    response['user_info'] = None

            case pam.PAM_AUTH_ERR | pam.PAM_USER_UNKNOWN:
                # We have to squash AUTH_ERR and USER_UNKNOWN into a generic response
                # to prevent unauthenticated remote clients from guessing valid usernames.
                response['response_type'] = AuthResp.AUTH_ERR
            case pam.PAM_ACCT_EXPIRED | pam.PAM_NEW_AUTHTOK_REQD | pam.PAM_CRED_EXPIRED:
                response['response_type'] = AuthResp.EXPIRED.name
            case _:
                # This is unexpected and so we should generate a debug message
                # so that we can better handle in the future.
                self.logger.debug(
                    '%s: unexpected response code [%d] to authentication request',
                    mechanism, resp['pam_response']['code']
                )
                response['response_type'] = AuthResp.AUTH_ERR

        return response

    @private
    @pass_app()
    async def get_login_user(self, app, username, password, mechanism):
        """
        This is a private endpoint that performs the actual validation of username/password
        combination and returns user information and whether additional OTP is required.
        """
        otp_required = False
        resp = await self.middleware.call(
            'auth.authenticate_plain',
            username, password,
            mechanism == AuthMech.API_KEY_PLAIN,
            app=app
        )
        if mechanism == AuthMech.PASSWORD_PLAIN and resp['pam_response']['code'] == pam.PAM_SUCCESS:
            twofactor_auth = await self.middleware.call('auth.twofactor.config')
            if twofactor_auth['enabled'] and '2FA' in resp['user_data']['account_attributes']:
                otp_required = True

        return resp | {'otp_required': otp_required}

    @cli_private
    @api_method(AuthLegacyApiKeyLoginArgs, AuthLegacyResult, authentication_required=False)
    @pass_app()
    async def login_with_api_key(self, app, api_key):
        """
        Authenticate session using API Key.
        """
        try:
            key_id = int(api_key.split('-')[0])
            key_entry = await self.middleware.call('api_key.query', [['id', '=', key_id]])
        except Exception:
            key_entry = None

        if not key_entry:
            await asyncio.sleep(random.uniform(1, 2))
            await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                'credentials': {
                    'credentials': 'API_KEY',
                    'credentials_data': {
                        'username': None,
                        'api_key': api_key,
                    }
                },
                'error': 'Invalid API key'
            }, False)
            return False

        resp = await self.login_ex(app, {
            'mechanism': AuthMech.API_KEY_PLAIN,
            'username': key_entry[0]['username'],
            'api_key': api_key,
            'login_options': {'user_info': False},
        })

        return resp['response_type'] == AuthResp.SUCCESS

    @cli_private
    @api_method(AuthLegacyTokenLoginArgs, AuthLegacyResult, authentication_required=False)
    @pass_app()
    async def login_with_token(self, app, token_str):
        """
        Authenticate session using token generated with `auth.generate_token`.
        """
        resp = await self.login_ex(app, {
            'mechanism': AuthMech.TOKEN_PLAIN,
            'token': token_str,
            'login_options': {'user_info': False},
        })
        return resp['response_type'] == AuthResp.SUCCESS

    @cli_private
    @api_method(AuthSessionLogoutArgs, AuthSessionLogoutResult, authorization_required=False)
    @pass_app()
    async def logout(self, app):
        """
        Deauthenticates an app and if a token exists, removes that from the
        session.
        """
        await self.session_manager.logout(app)
        return True

    @api_method(AuthMeArgs, AuthMeResult, authorization_required=False)
    @pass_app()
    async def me(self, app):
        """
        Returns currently logged-in user.
        """
        user = await self._me(app)

        if attr := await self._attributes(user):
            attributes = attr['attributes']
        else:
            attributes = {}

        try:
            twofactor_config = await self.middleware.call('user.twofactor_config', user['pw_name'])
        except Exception:
            self.logger.error('%s: failed to look up 2fa details', exc_info=True)
            twofactor_config = None

        return {**user, 'attributes': attributes, 'two_factor_config': twofactor_config}

    @api_method(AuthSetAttributeArgs, AuthSetAttributeResult, authorization_required=False)
    @pass_app()
    async def set_attribute(self, app, key, value):
        """
        Set current user's `attributes` dictionary `key` to `value`.

        e.g. Setting key="foo" value="var" will result in {"attributes": {"foo": "bar"}}
        """
        user = await self._me(app)

        async with self._attributes_lock:
            if attrs := await self._attributes(user):
                await self.middleware.call('datastore.update', 'account.bsdusers_webui_attribute', attrs['id'],
                                           {'attributes': {**attrs['attributes'], key: value}})
            else:
                await self.middleware.call('datastore.insert', 'account.bsdusers_webui_attribute', {
                    'uid': user['pw_uid'],
                    'attributes': {key: value},
                })

    _attributes_lock = asyncio.Lock()

    async def _me(self, app):
        credentials = app.authenticated_credentials
        if isinstance(credentials, TokenSessionManagerCredentials):
            if root_credentials := credentials.token.root_credentials():
                credentials = root_credentials

        if not isinstance(credentials, UserSessionManagerCredentials):
            raise CallError(f'You are logged in using {credentials.class_name()}')

        username = credentials.user['username']

        return {
            **(await self.middleware.call('user.get_user_obj', {'username': username})),
            'privilege': credentials.user['privilege'],
            'account_attributes': credentials.user['account_attributes']
        }

    async def _attributes(self, user):
        try:
            return await self.middleware.call('datastore.query', 'account.bsdusers_webui_attribute',
                                              [['uid', '=', user['pw_uid']]], {'get': True})
        except MatchNotFound:
            return None


async def check_permission(middleware, app):
    """Authenticates connections coming from loopback and from root user."""
    origin = app.origin
    if origin is None:
        return

    if origin.is_unix_family:
        if origin.uid == 0:
            user = await middleware.call('auth.authenticate_root')
        else:
            try:
                user_info = (await middleware.call(
                    'datastore.query',
                    'account.bsdusers',
                    [['uid', '=', origin.uid]],
                    {'get': True, 'prefix': 'bsdusr_', 'select': ['id', 'uid', 'username']},
                )) | {'local': True}
                query = {'username': user_info.pop('username')}
            except MatchNotFound:
                query = {'uid': origin.uid}
                user_info = {'id': None, 'uid': None, 'local': False}

            user = await middleware.call('auth.authenticate_user', query, user_info, False)
            if user is None:
                return

        await AuthService.session_manager.login(app, UnixSocketSessionManagerCredentials(user))


def setup(middleware):
    middleware.event_register('auth.sessions', 'Notification of new and removed sessions.')
    middleware.register_hook('core.on_connect', check_permission)
