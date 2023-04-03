import asyncio
from datetime import datetime, timedelta
import errno
import time
import warnings

import psutil

from middlewared.auth import (SessionManagerCredentials, UserSessionManagerCredentials,
                              UnixSocketSessionManagerCredentials, RootTcpSocketSessionManagerCredentials,
                              LoginPasswordSessionManagerCredentials, ApiKeySessionManagerCredentials,
                              TrueNasNodeSessionManagerCredentials)
from middlewared.schema import accepts, Any, Bool, Datetime, Dict, Int, Patch, returns, Str
from middlewared.service import (
    Service, filterable, filterable_returns, filter_list, no_auth_required,
    pass_app, private, cli_private, CallError, throttle,
)
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.nginx import get_peer_process
from middlewared.utils.origin import UnixSocketOrigin, TCPIPOrigin
from middlewared.utils.crypto import generate_token


def throttle_condition(middleware, app, *args, **kwargs):
    return app is None or (app and app.authenticated), None


class TokenManager:
    def __init__(self):
        self.tokens = {}

    def create(self, ttl, attributes, match_origin, parent_credentials):
        credentials = parent_credentials
        if isinstance(credentials, TokenSessionManagerCredentials):
            if root_credentials := credentials.token.root_credentials():
                credentials = root_credentials

        token = generate_token(48, url_safe=True)
        self.tokens[token] = Token(self, token, ttl, attributes, match_origin, credentials)
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


class Token:
    def __init__(self, manager, token, ttl, attributes, match_origin, parent_credentials):
        self.manager = manager
        self.token = token
        self.ttl = ttl
        self.attributes = attributes
        self.match_origin = match_origin
        self.parent_credentials = parent_credentials

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

    def login(self, app, credentials):
        if app.authenticated:
            self.sessions[app.session_id].credentials = credentials
            app.authenticated_credentials = credentials
            return

        session = Session(self, credentials, app)
        self.sessions[app.session_id] = session

        app.authenticated = True
        app.authenticated_credentials = credentials

        app.register_callback("on_message", self._app_on_message)
        app.register_callback("on_close", self._app_on_close)

        if not is_internal_session(session):
            self.middleware.send_event("auth.sessions", "ADDED", fields=dict(id=app.session_id, **session.dump()))

    def logout(self, app):
        session = self.sessions.pop(app.session_id, None)

        if session is not None:
            session.credentials.logout()

            if not is_internal_session(session):
                self.middleware.send_event("auth.sessions", "REMOVED", fields=dict(id=app.session_id))

        app.authenticated = False

    def _app_on_message(self, app, message):
        session = self.sessions.get(app.session_id)
        if session is None:
            app.authenticated = False
            return

        if not session.credentials.is_valid():
            self.logout(app)
            return

        session.credentials.notify_used()

    def _app_on_close(self, app):
        self.logout(app)


def dump_credentials(credentials):
    return {
        "credentials": credentials.class_name(),
        "credentials_data": credentials.dump(),
    }


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
            "created_at": datetime.utcnow() - timedelta(seconds=time.monotonic() - self.created_at),
        }


class TokenSessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, token_manager, token):
        self.token_manager = token_manager
        self.token = token

    def is_valid(self):
        return self.token.is_valid()

    def authorize(self, method, resource):
        return self.token.parent_credentials.authorize(method, resource)

    def notify_used(self):
        self.token.notify_used()

    def logout(self):
        self.token_manager.destroy(self.token)

    def dump(self):
        return {
            "parent": dump_credentials(self.token.parent_credentials),
        }


def is_internal_session(session):
    if isinstance(session.app.origin, UnixSocketOrigin) and session.app.origin.uid == 0:
        return True

    if isinstance(session.app.authenticated_credentials, (
        RootTcpSocketSessionManagerCredentials,
        TrueNasNodeSessionManagerCredentials,
    )):
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

    @filterable
    @filterable_returns(Dict(
        'session',
        Str('id'),
        Bool('current'),
        Bool('internal'),
        Str('origin'),
        Str('credentials'),
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

    @accepts(Str('id'))
    @returns(Bool(description='Is `true` if session was terminated successfully'))
    async def terminate_session(self, id):
        """
        Terminates session `id`.
        """
        session = self.session_manager.sessions.get(id)
        if session is None:
            return False

        await session.app.response.close()

    @accepts()
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

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts(Str('username'), Str('password'))
    @returns(Bool(description='Is `true` if `username` was successfully validated with provided `password`'))
    async def check_user(self, username, password):
        """
        Verify username and password
        """
        return await self.check_password(username, password)

    @accepts(Str('username'), Str('password'))
    @returns(Bool(description='Is `true` if `username` was successfully validated with provided `password`'))
    async def check_password(self, username, password):
        """
        Verify username and password
        """
        return await self.middleware.call('auth.authenticate', username, password) is not None

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
    @throttle(seconds=2, condition=throttle_condition)
    @accepts(Str('username'), Str('password'))
    @returns(Bool('two_factor_auth_enabled', description='Is `true` if 2FA is enabled'))
    async def two_factor_auth(self, username, password):
        """
        Returns true if two factor authorization is required for authorizing user's login.
        """
        return await self.check_user(username, password) and (
            await self.middleware.call('auth.twofactor.config')
        )['enabled'] and (
            await self.middleware.call(
                'user.query', [['username', '=', username], ['twofactor_auth_configured', '=', True]]
            )
        )

    @cli_private
    @no_auth_required
    @accepts(Str('username'), Str('password', private=True), Str('otp_token', null=True, default=None))
    @returns(Bool('successful_login'))
    @pass_app()
    async def login(self, app, username, password, otp_token):
        """
        Authenticate session using username and password.
        `otp_token` must be specified if two factor authentication is enabled.
        """
        user = await self.get_login_user(username, password, otp_token)
        if user is not None:
            self.session_manager.login(app, LoginPasswordSessionManagerCredentials(user))
            return True

        return False

    @private
    async def get_login_user(self, username, password, otp_token=None):
        user = await self.middleware.call('auth.authenticate', username, password)
        twofactor_auth = await self.middleware.call('auth.twofactor.config')

        if twofactor_auth['enabled'] and (
            await self.middleware.call(
                'user.query', [['username', '=', username], ['twofactor_auth_configured', '=', True]]
            )
        ):
            # We should run user.verify_twofactor_token regardless of check_user result to prevent guessing
            # passwords with a timing attack
            if not await self.middleware.call('user.verify_twofactor_token', username, otp_token):
                user = None

        return user

    @cli_private
    @no_auth_required
    @accepts(Str('api_key'))
    @returns(Bool('successful_login'))
    @pass_app()
    async def login_with_api_key(self, app, api_key):
        """
        Authenticate session using API Key.
        """
        if api_key_object := await self.middleware.call('api_key.authenticate', api_key):
            self.session_manager.login(app, ApiKeySessionManagerCredentials(api_key_object))
            return True

        return False

    @cli_private
    @no_auth_required
    @accepts(Str('token'))
    @returns(Bool('successful_login'))
    @pass_app()
    async def login_with_token(self, app, token):
        """
        Authenticate session using token generated with `auth.generate_token`.
        """
        token = self.token_manager.get(token, app.origin)
        if token is None:
            return False

        if token.attributes:
            return None

        self.session_manager.login(app, TokenSessionManagerCredentials(self.token_manager, token))
        return True

    @private
    @no_auth_required
    @pass_app()
    async def token(self, app, token):
        warnings.warn("`auth.token` has been deprecated. Use `api.login_with_token`", DeprecationWarning)
        return await self.login_with_token(app, token)

    @cli_private
    @accepts()
    @returns(Bool('successful_logout'))
    @pass_app()
    async def logout(self, app):
        """
        Deauthenticates an app and if a token exists, removes that from the
        session.
        """
        self.session_manager.logout(app)
        return True

    @accepts()
    @returns(
        Patch(
            'user_information',
            'current_user_information',
            ('add', Dict('attributes', additional_attrs=True)),
        )
    )
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

        return {**user, 'attributes': attributes}

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

        return await self.middleware.call('user.get_user_obj', {'username': credentials.user['username']})

    async def _attributes(self, user):
        try:
            return await self.middleware.call('datastore.query', 'account.bsdusers_webui_attribute',
                                              [['uid', '=', user['pw_uid']]], {'get': True})
        except MatchNotFound:
            return None


def check_permission(middleware, app):
    """Authenticates connections coming from loopback and from root user."""
    origin = app.origin
    if origin is None:
        return

    if isinstance(origin, UnixSocketOrigin):
        if origin.uid == 0:
            user = middleware.call_sync('auth.authenticate_root')
        else:
            try:
                query = {
                    'username': middleware.call_sync(
                        'datastore.query',
                        'account.bsdusers',
                        [['uid', '=', origin.uid]],
                        {'get': True, 'prefix': 'bsdusr_'},
                    )['username'],
                }
                local = True
            except MatchNotFound:
                query = {'uid': origin.uid}
                local = False

            user = middleware.call_sync('auth.authenticate_user', query, local)
            if user is None:
                return

        AuthService.session_manager.login(app, UnixSocketSessionManagerCredentials(user))
        return

    if isinstance(origin, TCPIPOrigin):
        if not (origin.addr.startswith('127.') or origin.addr == '::1'):
            return

        # This is an expensive operation, but it is only performed for localhost TCP connections which are rare
        if process := get_peer_process(origin.addr, origin.port):
            try:
                euid = process.uids().effective
            except psutil.NoSuchProcess:
                pass
            else:
                if euid == 0:
                    AuthService.session_manager.login(app, RootTcpSocketSessionManagerCredentials())
                    return


def setup(middleware):
    middleware.event_register('auth.sessions', 'Notification of new and removed sessions.')
    middleware.register_hook('core.on_connect', check_permission, sync=True)
