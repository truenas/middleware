import crypt
from datetime import datetime, timedelta
import random
import re
import socket
import string
import subprocess
import time

from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import Service, filterable, filter_list, no_auth_required, pass_app, private
from middlewared.utils import Popen


class TokenManager:
    def __init__(self):
        self.tokens = {}

    def create(self, ttl, attributes=None):
        token = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
        self.tokens[token] = Token(self, token, ttl, attributes)
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
    def __init__(self, manager, token, ttl, attributes):
        self.manager = manager
        self.token = token
        self.ttl = ttl
        self.attributes = attributes

        self.last_used_at = time.monotonic()

    def is_valid(self):
        return time.monotonic() < self.last_used_at + self.ttl

    def notify_used(self):
        self.last_used_at = time.monotonic()


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.sessions_last_sent_last_active = {}

        self.middleware = None

    def login(self, app, credentials):
        if app.authenticated:
            self.sessions[app.session_id].credentials = credentials
            return

        origin = self._get_origin(app)

        session = Session(self, origin, credentials)
        self.sessions[app.session_id] = session

        app.authenticated = True

        app.register_callback("on_message", self._app_on_message)
        app.register_callback("on_close", self._app_on_close)

        if not is_local(session):
            self.middleware.send_event("auth.sessions", "ADDED", fields=dict(id=app.session_id, **session.dump()))

            self.sessions_last_sent_last_active[app.session_id] = session.last_active

    def logout(self, app):
        session = self.sessions.pop(app.session_id, None)

        if session is not None:
            session.credentials.logout()

            if not is_local(session):
                self.middleware.send_event("auth.sessions", "REMOVED", fields=dict(id=app.session_id))

        app.authenticated = False

        self.sessions_last_sent_last_active.pop(app.session_id, None)

    def _get_origin(self, app):
        sock = app.request.transport.get_extra_info("socket")
        if sock.family == socket.AF_UNIX:
            return "UNIX_SOCKET"

        remote_addr, remote_port = app.request.transport.get_extra_info("peername")
        if remote_addr.startswith("127.") or remote_addr == "::1":
            try:
                remote_addr, remote_port = (app.request.headers["X-Real-Remote-Addr"],
                                            int(app.request.headers["X-Real-Remote-Port"]))
            except (KeyError, ValueError):
                pass

        return f"{remote_addr}:{remote_port}"

    def _app_on_message(self, app, message):
        session = self.sessions.get(app.session_id)
        if session is None:
            app.authenticated = False
            return

        if not session.credentials.is_valid():
            self.logout(app)
            return

        session.notify_used()

        session.credentials.notify_used()

        if not is_local(session):
            if session.last_active - self.sessions_last_sent_last_active[app.session_id] > 10:
                self.middleware.send_event("auth.sessions", "CHANGED", fields=dict(id=app.session_id, **session.dump()))

                self.sessions_last_sent_last_active[app.session_id] = session.last_active

    def _app_on_close(self, app):
        self.logout(app)


class Session:
    def __init__(self, manager, origin, credentials):
        self.manager = manager
        self.origin = origin
        self.credentials = credentials

        self.created_at = time.monotonic()
        self.last_active = time.monotonic()

    def notify_used(self):
        self.last_active = time.monotonic()

    def dump(self):
        return {
            "origin": self.origin,
            "credentials": re.sub(
                "([A-Z])",
                "_\\1",
                self.credentials.__class__.__name__.replace("SessionManagerCredentials", "")
            ).lstrip("_").upper(),
            "created_at": datetime.utcnow() - timedelta(seconds=time.monotonic() - self.created_at),
            "last_active": datetime.utcnow() - timedelta(seconds=time.monotonic() - self.last_active),
        }


class SessionManagerCredentials:
    def login(self):
        pass

    def is_valid(self):
        return True

    def notify_used(self):
        pass

    def logout(self):
        pass


class UnixSocketSessionManagerCredentials(SessionManagerCredentials):
    pass


class RootTcpSocketSessionManagerCredentials(SessionManagerCredentials):
    pass


class LoginPasswordSessionManagerCredentials(SessionManagerCredentials):
    pass


class TokenSessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, token_manager, token):
        self.token_manager = token_manager
        self.token = token

    def logout(self):
        self.token_manager.destroy(self.token)


def is_local(session):
    return session.origin == "UNIX_SOCKET" or session.origin.startswith("127.") or session.origin == "::1"


class AuthService(Service):
    session_manager = SessionManager()

    token_manager = TokenManager()

    def __init__(self, *args, **kwargs):
        super(AuthService, self).__init__(*args, **kwargs)
        self.session_manager.middleware = self.middleware

    @filterable
    def sessions(self, filters=None, options=None):
        """
        Returns list of active auth sessions.

        Example of return value:

        [
            {
                "id": "NyhB1J5vjPjIV82yZ6caU12HLA1boDJcZNWuVQM4hQWuiyUWMGZTz2ElDp7Yk87d",
                "origin": "192.168.0.3:40392",
                "credentials": "TOKEN",
                "created_at": {"$date": 1545842426070},
                "last_active": {"$date": 1545842487816}
            }
        ]

        `credentials` can be `LOGIN_PASSWORD` or `TOKEN` depending on what authentication method was used
        """
        return filter_list(
            [
                dict(id=session_id, **session.dump())
                for session_id, session in sorted(self.session_manager.sessions.items(),
                                                  key=lambda t: t[1].created_at)
                if not is_local(session)
            ],
            filters,
            options,
        )

    @accepts(Str('username'), Str('password'))
    async def check_user(self, username, password):
        """
        Verify username and password
        """
        if username != 'root':
            return False
        try:
            user = await self.middleware.call('datastore.query', 'account.bsdusers',
                                              [('bsdusr_username', '=', username)], {'get': True})
        except IndexError:
            return False
        if user['bsdusr_unixhash'] in ('x', '*'):
            return False
        return crypt.crypt(password, user['bsdusr_unixhash']) == user['bsdusr_unixhash']

    @accepts(Int('ttl', default=600, null=True), Dict('attrs', additional_attrs=True))
    def generate_token(self, ttl=None, attrs=None):
        """
        Generate a token to be used for authentication.

        `ttl` stands for Time To Live, in seconds. The token will be invalidated if the connection
        has been inactive for a time greater than this.

        `attrs` is a general purpose object/dictionary to hold information about the token.
        """
        if ttl is None:
            ttl = 600

        token = self.token_manager.create(ttl, attrs)

        return token.token

    @private
    def get_token(self, token_id):
        try:
            return {
                'attributes': self.token_manager.tokens[token_id]
            }
        except KeyError:
            return None

    @no_auth_required
    @accepts(Str('username'), Str('password'))
    @pass_app
    async def login(self, app, username, password):
        """Authenticate session using username and password.
        Currently only root user is allowed.
        """
        valid = await self.check_user(username, password)
        if valid:
            self.session_manager.login(app, LoginPasswordSessionManagerCredentials())
        return valid

    @accepts()
    @pass_app
    async def logout(self, app):
        """
        Deauthenticates an app and if a token exists, removes that from the
        session.
        """
        self.session_manager.logout(app)
        return True

    @no_auth_required
    @accepts(Str('token'))
    @pass_app
    def token(self, app, token):
        """Authenticate using a given `token` id."""
        token = self.token_manager.get(token)
        if token is None:
            return False

        self.session_manager.login(app, TokenSessionManagerCredentials(self.token_manager, token))
        return True


async def check_permission(middleware, app):
    """
    Authenticates connections comming from loopback and from
    root user.
    """
    sock = app.request.transport.get_extra_info('socket')
    if sock.family == socket.AF_UNIX:
        # Unix socket is only allowed for root
        AuthService.session_manager.login(app, UnixSocketSessionManagerCredentials())
        return

    remote_addr, remote_port = app.request.transport.get_extra_info('peername')

    if not (remote_addr.startswith('127.') or remote_addr == '::1'):
        return

    remote = '{0}:{1}'.format(remote_addr, remote_port)

    proc = await Popen([
        '/usr/bin/sockstat', '-46c', '-p', str(remote_port)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    data = await proc.communicate()
    for line in data[0].strip().splitlines()[1:]:
        cols = line.decode().split()
        if cols[-2] == remote and cols[0] == 'root':
            AuthService.session_manager.login(app, RootTcpSocketSessionManagerCredentials())
            break


def setup(middleware):
    middleware.register_hook('core.on_connect', check_permission, sync=True)
