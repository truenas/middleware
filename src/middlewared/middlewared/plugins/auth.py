import crypt
import time
import uuid

from middlewared.schema import Int, Str, accepts
from middlewared.service import Service, no_auth_required, pass_app


class AuthService(Service):

    def __init__(self, *args, **kwargs):
        super(AuthService, self).__init__(*args, **kwargs)
        self.auth_tokens = {}

    @accepts(Str('username'), Str('password'))
    def check_user(self, username, password):
        """Authenticate session using username and password.
        Currently only root user is allowed.
        """
        if username != 'root':
            return False
        try:
            user = self.middleware.call('datastore.query', 'account.bsdusers', [('bsdusr_username', '=', username)], {'get': True})
        except IndexError:
            return False
        if user['bsdusr_unixhash'] in ('x', '*'):
            return False
        return crypt.crypt(password, user['bsdusr_unixhash']) == user['bsdusr_unixhash']

    @accepts(Int('ttl', required=False))
    def generate_token(self, ttl=None):
        """Generate a token to be used for authentication."""
        if ttl is None:
            ttl = 600
        token = str(uuid.uuid4())
        self.auth_tokens[token] = {
            'added': int(time.time()),
            'last': int(time.time()),
            'ttl': ttl,
        }
        return token

    @no_auth_required
    @accepts(Str('username'), Str('password'))
    @pass_app
    def login(self, app, username, password):
        valid = self.check_user(username, password)
        if valid:
            app.authenticated = True
        return valid

    @no_auth_required
    @accepts(Str('token'))
    @pass_app
    def token(self, app, token):
        attrs = self.auth_tokens.get(token)
        if attrs is None:
            return False
        if int(time.time()) - attrs['ttl'] < attrs['last']:
            attrs['last'] = int(time.time())
            app.authenticated = True
            return True
        else:
            del self.auth_tokens[token]
            return False
