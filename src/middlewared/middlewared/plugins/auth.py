import asyncio
import random
from datetime import timedelta
import errno
import os
import pam
import time

from middlewared.api import api_method
from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketAppEvent
from middlewared.api.current import (
    AuthLoginExArgs, AuthLoginExResult,
    AuthMeArgs, AuthMeResult,
)
from middlewared.auth import (UserSessionManagerCredentials, UnixSocketSessionManagerCredentials,
                              ApiKeySessionManagerCredentials, LoginPasswordSessionManagerCredentials,
                              TrueNasNodeSessionManagerCredentials, TokenSessionManagerCredentials,
                              dump_credentials, AuthenticationContext)
from middlewared.plugins.account_.constants import MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE
from middlewared.schema import accepts, Any, Bool, Datetime, Dict, Int, Password, returns, Str
from middlewared.service import (
    Service, filterable, filterable_returns, filter_list, no_auth_required, no_authz_required,
    pass_app, private, cli_private, CallError,
)
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.auth import AuthMech, AuthResp
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
        self.authentication_context = AuthenticationContext(pam_hdl=pam.pam())
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

    if isinstance(session.app.authenticated_credentials, TrueNasNodeSessionManagerCredentials):
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

    @filterable(roles=['AUTH_SESSIONS_READ'])
    @filterable_returns(Dict(
        'session',
        Str('id'),
        Bool('current'),
        Bool('internal'),
        Str('origin'),
        Str('credentials'),
        Dict('credentials_data', additional_attrs=True),
        Datetime('created_at'),
    ))
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

    @accepts(Str('id'), roles=['AUTH_SESSIONS_WRITE'])
    @returns(Bool(description='Is `true` if session was terminated successfully'))
    async def terminate_session(self, id_):
        """
        Terminates session `id`.
        """
        session = self.session_manager.sessions.get(id_)
        if session is None:
            return False

        self.token_manager.destroy_by_session_id(id_)

        await session.app.ws.close()

    @accepts(roles=['AUTH_SESSIONS_WRITE'])
    @returns()
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

    @cli_private
    @accepts(Str('username'), Password('password'))
    @returns(Bool(description='Is `true` if `username` was successfully validated with provided `password`'))
    async def check_user(self, username, password):
        """
        Verify username and password
        """
        return await self.check_password(username, password)

    @cli_private
    @accepts(Str('username'), Password('password'))
    @returns(Bool(description='Is `true` if `username` was successfully validated with provided `password`'))
    async def check_password(self, username, password):
        """
        Verify username and password
        """
        return await self.middleware.call('auth.authenticate_plain', username, password) is not None

    @no_auth_required
    @accepts(
        Int('ttl', default=600, null=True),
        Dict('attrs', additional_attrs=True),
        Bool('match_origin', default=False),
    )
    @returns(Str('token'))
    @pass_app(rest=True)
    def generate_token(self, app, ttl, attrs, match_origin):
        """
        Generate a token to be used for authentication.

        `ttl` stands for Time To Live, in seconds. The token will be invalidated if the connection
        has been inactive for a time greater than this.

        `attrs` is a general purpose object/dictionary to hold information about the token.

        `match_origin` will only allow using this token from the same IP address or with the same user UID.
        """
        if not app.authenticated:
            raise CallError('Not authenticated', errno.EACCES)

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

    @no_auth_required
    @accepts(Str('username'), Str('password'))
    @returns(Bool('two_factor_auth_enabled', description='Is `true` if 2FA is enabled'))
    async def two_factor_auth(self, username, password):
        """
        Returns true if two-factor authorization is required for authorizing user's login.
        """
        user_authenticated = await self.middleware.call('auth.authenticate_plain', username, password)
        return user_authenticated and (
            await self.middleware.call('auth.twofactor.config')
        )['enabled'] and '2FA' in user_authenticated['account_attributes']

    @cli_private
    @no_auth_required
    @accepts(Str('username'), Password('password'), Password('otp_token', null=True, default=None))
    @returns(Bool('successful_login'))
    @pass_app()
    async def login(self, app, username, password, otp_token):
        """
        Authenticate session using username and password.
        `otp_token` must be specified if two factor authentication is enabled.
        """

        resp = await self.login_ex(app, {
            'mechanism': AuthMech.PASSWORD_PLAIN.name,
            'username': username,
            'password': password
        })

        match resp['response_type']:
            case AuthResp.SUCCESS.name:
                return True
            case AuthResp.OTP_REQUIRED.name:
                if otp_token is None:
                    return False

                otp_resp = await self.login_ex({
                    'mechanism': AuthMech.OTP_TOKEN.name,
                    'otp_token': otp_token
                })
                return otp_resp['response_type'] == AuthResp.SUCCESS.name
            case _:
                return False

    @private
    def libpam_authenticate(self, username, password, pam_service=MIDDLEWARE_PAM_SERVICE):
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
                return {'code': pam.PAM_ABORT, 'reason': 'Failed to generate PAM service file'}

        p = self.session_manager.authentication_context.pam_hdl
        p.authenticate(username, password, service=os.path.basename(pam_service))
        return {'code': p.code, 'reason': p.reason}

    @cli_private
    @no_auth_required
    @api_method(AuthLoginExArgs, AuthLoginExResult)
    @pass_app()
    async def login_ex(self, app, data):
        """
        Authenticate using one of a variety of mechanisms

        NOTE: mechanisms with a _PLAIN suffix indicate that they involve
        passing plain-text passwords or password-equivalent strings and
        should not be used on untrusted / insecure transport. Available
        mechanisms will be expanded in future releases.

        params:
            mechanism: the mechanism by which to authenticate to the backend
            the exact parameters to use vary by mechanism and are described
            below

            PASSWORD_PLAIN
            username: username with which to authenticate
            password: password with which to authenticate

            API_KEY_PLAIN
            username: username with which to authenticate
            api_key: API key string

            AUTH_TOKEN_PLAIN
            token: authentication token string

            OTP_TOKEN
            otp_token: one-time password token. This is only permitted if
            a previous auth.login_ex call responded with "OTP_REQUIRED".

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

        returns:
            dictionary containing the following keys:

            response_type: string indicating the results of the current authentication
                mechanism. This is used to inform client of nature of authentication
                error or whether further action will be required in order to complete
                authentication.

            <additional keys per response_type>

        Notes about response types:

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
        mechanism = data['mechanism']
        auth_ctx = self.session_manager.authentication_context
        login_fn = self.session_manager.login
        next_mech = auth_ctx.next_mech
        response = {'response_type': AuthResp.AUTH_ERR.name}

        if next_mech and mechanism != next_mech:
            raise CallError(
                f'{mechanism}: authentication in progress. Expected [{next_mech}]',
                errno.EBUSY
            )

        if next_mech is None and mechanism == AuthMech.OTP_TOKEN.name:
            raise CallError(f'{mechanism}: no authentication in progress', errno.EINVAL)

        match mechanism:
            case AuthMech.PASSWORD_PLAIN.name:
                # Both of these mechanisms are de-factor username + password
                # combinations and pass through libpam.
                resp = await self.get_login_user(
                    data['username'],
                    data['password'],
                    mechanism
                )
                if resp['otp_required']:
                    # A one-time password is required for this user account and so
                    # we should request it from API client.
                    auth_ctx.next_mech = AuthMech.OTP_TOKEN.name
                    auth_ctx.user_data = resp['user_data']
                    return {
                        'response_type': AuthResp.OTP_REQUIRED.name,
                        'username': resp['user_data']['username']
                    }

                if resp['pam_response']['code'] == pam.PAM_SUCCESS:
                    await login_fn(app, LoginPasswordSessionManagerCredentials(resp['user_data']))
                else:
                    await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                        "credentials": {
                            "credentials": 'LOGIN_PASSWORD',
                            "credentials_data": {'username': data['username']},
                        },
                        "error": resp['pam_response']['reason']
                    }, False)

            case AuthMech.API_KEY_PLAIN.name:
                # API key that we receive over wire is concatenation of the
                # datastore `id` of the particular key with the key itself,
                # delimited by a dash. <id>-<key>.
                resp = await self.get_login_user(
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
                        {'get': True, 'select': ['id', 'name', 'key']}
                    )
                    hash = key.pop('key')
                except Exception:
                    key = None

                if resp['pam_response']['code'] == pam.PAM_SUCCESS:
                    if hash.startswith('$pbkdf2-sha256'):
                        # Legacy API key with insufficient iterations. Since we
                        # know that the plain-text we have here is correct, we can
                        # use it to update the hash in backend.
                        await self.middleware.call('api_key.update_hash', data['api_key'])

                    await login_fn(app, ApiKeySessionManagerCredentials(resp['user_data'], key))
                else:
                    await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                        "credentials": {
                            "credentials": 'LOGIN_API_KEY',
                            "credentials_data": {
                                "username": data['username'],
                                "api_key": key,
                            }
                        },
                        "error": resp['pam_response']['reason'],
                    }, False)

            case AuthMech.OTP_TOKEN.name:
                # We've received a one-time password token based in response to our
                # response to an earlier authentication attempt. This means our auth
                # context has user information. We don't re-request username from the
                # client as this would open possibility of user trivially bypassing
                # 2FA.
                otp_ok = await self.middleware.call(
                    'user.verify_twofactor_token',
                    auth_ctx.user_data['username'],
                    data['otp_token'],
                )
                resp = {
                    'pam_response': {
                        'code': pam.PAM_SUCCESS if otp_ok else pam.PAM_AUTH_ERR,
                        'reason': None
                    }
                }
                # get reference to user data
                user = auth_ctx.user_data

                # reset the auth_ctx state
                auth_ctx.next_mech = None
                auth_ctx.user_data = None

                if otp_ok:
                    # Per feedback to NEP-053 it was decided to only request second
                    # factor for password-based logins (not user-linked API keys).
                    await login_fn(app, LoginPasswordSessionManagerCredentials(user))
                else:
                    # Add a sleep like pam_delay() would add for pam_oath
                    await asyncio.sleep(random.randint(1, 5))
                    await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                        "credentials": {
                            "credentials": "LOGIN_PASSWORD",
                            "credentials_data": {"username": user['username']},
                        },
                        "error": 'One-time token validation failed.'
                    }, False)

            case AuthMech.TOKEN_PLAIN.name:
                # We've received a authentication token that _should_ have been
                # generated by `auth.generate_token`. For consistency with other
                # authentication methods a failure delay has been added, but this
                # may be removed more safely than for other authentication methods
                # since the tokens are short-lived.
                token_str = data['token'],
                token = self.token_manager.get(token_str, app.origin)
                if token is None:
                    await asyncio.sleep(random.randint(1, 5))
                    await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                        "credentials": {
                            "credentials": "TOKEN",
                            "credentials_data": {
                                "token": token_str,
                            }
                        },
                        "error": "Invalid token",
                    }, False)
                    return response

                if token.attributes:
                    await asyncio.sleep(random.randint(1, 5))
                    await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                        "credentials": {
                            "credentials": "TOKEN",
                            "credentials_data": {
                                "token": token.token,
                            }
                        },
                        "error": "Bad token",
                    }, False)
                    return response

                await login_fn(app, TokenSessionManagerCredentials(self.token_manager, token))
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
                response['response_type'] = AuthResp.SUCCESS.name
            case pam.PAM_AUTH_ERR | pam.PAM_USER_UNKNOWN:
                # We have to squash AUTH_ERR and USER_UNKNOWN into a generic response
                # to prevent unauthenticated remote clients from guessing valid usernames.
                response['response_type'] = AuthResp.AUTH_ERR.name
            case pam.PAM_ACCT_EXPIRED | pam.PAM_NEW_AUTHTOK_REQD | pam.PAM_CRED_EXPIRED:
                response['response_type'] = AuthResp.EXPIRED.name
            case _:
                # This is unexpected and so we should generate a debug message
                # so that we can better handle in the future.
                self.logger.debug(
                    '%s: unexpected response code [%d] to authentication request',
                    mechanism, resp['pam_response']['code']
                )
                response['response_type'] = AuthResp.AUTH_ERR.name

        return response

    @private
    async def get_login_user(self, username, password, mechanism):
        otp_required = False
        resp = await self.middleware.call(
            'auth.authenticate_plain',
            username, password,
            mechanism == AuthMech.API_KEY_PLAIN.name
        )
        if mechanism == AuthMech.PASSWORD_PLAIN.name and resp['pam_response']['code'] == pam.PAM_SUCCESS:
            twofactor_auth = await self.middleware.call('auth.twofactor.config')
            if twofactor_auth['enabled'] and '2FA' in resp['user_data']['account_attributes']:
                otp_required = True

        return resp | {'otp_required': otp_required}

    @cli_private
    @no_auth_required
    @accepts(Password('api_key'))
    @returns(Bool('successful_login'))
    @pass_app()
    async def login_with_api_key(self, app, api_key):
        """
        Authenticate session using API Key.
        """
        try:
             key_id = int(api_key.split('-')[0])
        except Exception:
             return False

        key_entry = await self.middleware.call('api_key.query', [['id', '=', key_id]])
        if not key_entry:
            return False

        resp = await self.login_ex(app, {
            'mechanism': AuthMech.API_KEY_PLAIN.name,
            'username': key_entry[0]['username'],
            'api_key': api_key
        })
        self.logger.debug("XXX: resp: %s", resp)

        return resp['response_type'] == AuthResp.SUCCESS.name

    @cli_private
    @no_auth_required
    @accepts(Password('token'))
    @returns(Bool('successful_login'))
    @pass_app()
    async def login_with_token(self, app, token_str):
        """
        Authenticate session using token generated with `auth.generate_token`.
        """
        resp = await self.login_ex(app, {
            'mechanism': AuthMech.TOKEN_PLAIN.name,
            'token': token_str
        })
        return resp['response_type'] == AuthResp.SUCCESS.name

    @cli_private
    @accepts()
    @returns(Bool('successful_logout'))
    @pass_app()
    async def logout(self, app):
        """
        Deauthenticates an app and if a token exists, removes that from the
        session.
        """
        await self.session_manager.logout(app)
        return True

    @no_authz_required
    @api_method(AuthMeArgs, AuthMeResult)
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

    @no_authz_required
    @accepts(
        Str('key'),
        Any('value'),
    )
    @returns()
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

            user = await middleware.call('auth.authenticate_user', query, user_info)
            if user is None:
                return

        await AuthService.session_manager.login(app, UnixSocketSessionManagerCredentials(user))


def setup(middleware):
    middleware.event_register('auth.sessions', 'Notification of new and removed sessions.')
    middleware.register_hook('core.on_connect', check_permission)
