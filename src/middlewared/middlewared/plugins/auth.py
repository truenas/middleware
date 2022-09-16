from datetime import datetime, timedelta
import errno
import re
import socket
import struct
import time
import warnings

import psutil
import pyotp

from middlewared.schema import accepts, Bool, Datetime, Dict, Int, Patch, returns, Str
from middlewared.service import (
    ConfigService, Service, filterable, filterable_returns, filter_list, no_auth_required,
    pass_app, private, cli_private, CallError,
)
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.allowlist import Allowlist
from middlewared.utils.nginx import get_peer_process, get_remote_addr_port
from middlewared.utils.crypto import generate_token
from middlewared.validators import Range


class TokenManager:
    def __init__(self):
        self.tokens = {}

    def create(self, ttl, attributes, parent_credentials):
        attributes = attributes or {}

        token = generate_token(48, url_safe=True)
        self.tokens[token] = Token(self, token, ttl, attributes, parent_credentials)
        return self.tokens[token]

    def get(self, token):
        token = self.tokens.get(token)
        if token is None:
            return None

        if not token.is_valid():
            self.tokens.pop(token.token)
            return None

        return token

    def destroy(self, token):
        self.tokens.pop(token, None)


class Token:
    def __init__(self, manager, token, ttl, attributes, parent_credentials):
        self.manager = manager
        self.token = token
        self.ttl = ttl
        self.attributes = attributes
        self.parent_credentials = parent_credentials

        self.last_used_at = time.monotonic()

    def is_valid(self):
        return time.monotonic() < self.last_used_at + self.ttl

    def notify_used(self):
        self.last_used_at = time.monotonic()


class SessionManager:
    def __init__(self):
        self.sessions = {}

        self.middleware = None

    def login(self, app, credentials):
        if app.authenticated:
            self.sessions[app.session_id].credentials = credentials
            app.authenticated_credentials = credentials
            return

        origin = self._get_origin(app)

        session = Session(self, origin, credentials)
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

    def _get_origin(self, app):
        sock = app.request.transport.get_extra_info("socket")
        if sock.family == socket.AF_UNIX:
            return "UNIX_SOCKET"

        remote_addr, remote_port = get_remote_addr_port(app.request)

        if ":" in remote_addr:
            return f"[{remote_addr}]:{remote_port}"
        else:
            return f"{remote_addr}:{remote_port}"

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


class Session:
    def __init__(self, manager, origin, credentials):
        self.manager = manager
        self.origin = origin
        self.credentials = credentials

        self.created_at = time.monotonic()

    def dump(self):
        return {
            "origin": self.origin,
            "credentials": re.sub(
                "([A-Z])",
                "_\\1",
                self.credentials.__class__.__name__.replace("SessionManagerCredentials", "")
            ).lstrip("_").upper(),
            "created_at": datetime.utcnow() - timedelta(seconds=time.monotonic() - self.created_at),
        }


class SessionManagerCredentials:
    def login(self):
        pass

    def is_valid(self):
        return True

    def authorize(self, method, resource):
        return True

    def notify_used(self):
        pass

    def logout(self):
        pass


class UserSessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, user):
        self.user = user
        self.allowlist = Allowlist(user["privilege"]["allowlist"])

    def authorize(self, method, resource):
        return self.allowlist.authorize(method, resource)


class UnixSocketSessionManagerCredentials(UserSessionManagerCredentials):
    pass


class RootTcpSocketSessionManagerCredentials(SessionManagerCredentials):
    pass


class LoginPasswordSessionManagerCredentials(UserSessionManagerCredentials):
    pass


class ApiKeySessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, api_key):
        self.api_key = api_key

    def authorize(self, method, resource):
        return self.api_key.authorize(method, resource)


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


def is_internal_session(session):
    if session.origin == "UNIX_SOCKET":
        return True

    host, port = session.origin.rsplit(":", 1)
    host = host.strip("[]")
    port = int(port)

    if host in ["127.0.0.1", "::1"]:
        return True

    if host in ["169.254.10.1", "169.254.10.2", "169.254.10.20", "169.254.10.80"] and port <= 1024:
        return True

    return False


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
                "credentials": "TOKEN",
                "current": True,
                "internal": False,
                "created_at": {"$date": 1545842426070}
            }
        ]

        `credentials` can be `UNIX_SOCKET`, `ROOT_TCP_SOCKET`, `TRUENAS_NODE`, `LOGIN_PASSWORD` or `TOKEN`,
        depending on what authentication method was used.

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
    @accepts(Int('ttl', default=600, null=True), Dict('attrs', additional_attrs=True))
    @returns(Str('token'))
    @pass_app()
    def generate_token(self, app, ttl, attrs):
        """
        Generate a token to be used for authentication.

        `ttl` stands for Time To Live, in seconds. The token will be invalidated if the connection
        has been inactive for a time greater than this.

        `attrs` is a general purpose object/dictionary to hold information about the token.
        """
        if not app.authenticated:
            raise CallError('Not authenticated', errno.EACCESS)

        if ttl is None:
            ttl = 600

        token = self.token_manager.create(ttl, attrs, app.authenticated_credentials)

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
    def get_token_for_action(self, token_id, method, resource):
        if (token := self.token_manager.tokens.get(token_id)) is None:
            return None

        if token.attributes:
            return None

        if not token.parent_credentials.authorize(method, resource):
            return None

        return self.get_token(token_id)

    @private
    def get_token_for_shell_application(self, token_id):
        if (token := self.token_manager.tokens.get(token_id)) is None:
            return None

        if token.attributes:
            return None

        if not isinstance(token.parent_credentials, UserSessionManagerCredentials):
            return None

        if not token.parent_credentials.user['privilege']['web_shell']:
            return None

        return {
            'username': token.parent_credentials.user['username'],
        }

    @no_auth_required
    @accepts()
    @returns(Bool('two_factor_auth_enabled', description='Is `true` if 2FA is enabled'))
    async def two_factor_auth(self):
        """
        Returns true if two factor authorization is required for authorizing user's login.
        """
        return (await self.middleware.call('auth.twofactor.config'))['enabled']

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
        user = await self.middleware.call('auth.authenticate', username, password)
        twofactor_auth = await self.middleware.call('auth.twofactor.config')

        if twofactor_auth['enabled']:
            # We should run auth.twofactor.verify nevertheless of check_user result to prevent guessing
            # passwords with a timing attack
            if not await self.middleware.call(
                'auth.twofactor.verify',
                otp_token
            ):
                user = None

        if user is not None:
            self.session_manager.login(app, LoginPasswordSessionManagerCredentials(user))
            return True

        return False

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
        token = self.token_manager.get(token)
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


class TwoFactorAuthModel(sa.Model):
    __tablename__ = 'system_twofactorauthentication'

    id = sa.Column(sa.Integer(), primary_key=True)
    otp_digits = sa.Column(sa.Integer(), default=6)
    secret = sa.Column(sa.EncryptedText(), nullable=True, default=None)
    window = sa.Column(sa.Integer(), default=0)
    interval = sa.Column(sa.Integer(), default=30)
    services = sa.Column(sa.JSON(), default={})
    enabled = sa.Column(sa.Boolean(), default=False)


class TwoFactorAuthService(ConfigService):

    class Config:
        datastore = 'system.twofactorauthentication'
        datastore_extend = 'auth.twofactor.two_factor_extend'
        namespace = 'auth.twofactor'
        cli_namespace = 'auth.two_factor'

    ENTRY = Dict(
        'auth_twofactor_entry',
        Bool('enabled', required=True),
        Int('otp_digits', validators=[Range(min=6, max=8)], required=True),
        Int('window', validators=[Range(min=0)], required=True),
        Int('interval', validators=[Range(min=5)], required=True),
        Dict(
            'services',
            Bool('ssh', default=False),
            required=True
        ),
        Int('id', required=True),
        Str('secret', required=True, null=True),
    )

    @private
    async def two_factor_extend(self, data):
        for srv in ['ssh']:
            data['services'].setdefault(srv, False)

        return data

    @accepts(
        Patch(
            'auth_twofactor_entry', 'auth_twofactor_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'secret'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, data):
        """
        `otp_digits` represents number of allowed digits in the OTP.

        `window` extends the validity to `window` many counter ticks before and after the current one.

        `interval` is time duration in seconds specifying OTP expiration time from it's creation time.
        """
        old_config = await self.config()
        config = old_config.copy()

        config.update(data)

        if config['enabled'] and not config['secret']:
            # Only generate a new secret on `enabled` when `secret` is not already set.
            # This will aid users not setting secret up again on their mobiles.
            config['secret'] = await self.middleware.run_in_thread(
                self.generate_base32_secret
            )

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config['id'],
            config
        )

        await self.middleware.call('service.reload', 'ssh')

        return await self.config()

    @accepts(
        Str('token', null=True)
    )
    @returns(Bool('token_verified'))
    def verify(self, token):
        """
        Returns boolean true if provided `token` is successfully authenticated.
        """
        config = self.middleware.call_sync(f'{self._config.namespace}.config')
        if not config['enabled']:
            raise CallError('Please enable Two Factor Authentication first.')

        totp = pyotp.totp.TOTP(
            config['secret'], interval=config['interval'], digits=config['otp_digits']
        )
        return totp.verify(token, valid_window=config['window'])

    @accepts()
    @returns(Bool('successfully_renewed_secret'))
    def renew_secret(self):
        """
        Generates a new secret for Two Factor Authentication. Returns boolean true on success.
        """
        config = self.middleware.call_sync(f'{self._config.namespace}.config')
        if not config['enabled']:
            raise CallError('Please enable Two Factor Authentication first.')

        self.middleware.call_sync(
            'datastore.update',
            self._config.datastore,
            config['id'], {
                'secret': self.generate_base32_secret()
            }
        )

        if config['services']['ssh']:
            self.middleware.call_sync('service.reload', 'ssh')

        return True

    @accepts()
    @returns(Str(title='Provisioning URI'))
    async def provisioning_uri(self):
        """
        Returns the provisioning URI for the OTP. This can then be encoded in a QR Code and used to
        provision an OTP app like Google Authenticator.
        """
        config = await self.middleware.call(f'{self._config.namespace}.config')
        return pyotp.totp.TOTP(
            config['secret'], interval=config['interval'], digits=config['otp_digits']
        ).provisioning_uri(
            f'{await self.middleware.call("system.hostname")}@{await self.middleware.call("system.product_name")}',
            'iXsystems'
        )

    @private
    def generate_base32_secret(self):
        return pyotp.random_base32()


def check_permission(middleware, app):
    """Authenticates connections coming from loopback and from root user."""
    sock = app.request.transport.get_extra_info('socket')
    if sock.family == socket.AF_UNIX:
        peercred = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        pid, uid, gid = struct.unpack('3i', peercred)
        try:
            local_user = middleware.call_sync(
                'datastore.query',
                'account.bsdusers',
                [['bsdusr_uid', '=', uid]],
                {'get': True, 'prefix': 'bsdusr_'},
            )
        except MatchNotFound:
            return

        user = middleware.call_sync('auth.authenticate_local_user', local_user['id'], local_user['username'])
        AuthService.session_manager.login(app, UnixSocketSessionManagerCredentials(user))
        return

    remote_addr, remote_port = get_remote_addr_port(app.request)
    if not (remote_addr.startswith('127.') or remote_addr == '::1'):
        return

    # This is an expensive operation, but it is only performed for localhost TCP connections which are rare
    if process := get_peer_process(remote_addr, remote_port):
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
