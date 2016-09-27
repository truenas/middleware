import crypt
import time
import uuid

from middlewared.schema import Int, Str, accepts
from middlewared.service import Service, no_auth_required, pass_app


class AuthTokens(object):

    def __init__(self):
        # Keep two indexes, one by token id and one by session id
        self.__tokens = {}
        self.__sessionid_map = {}

    def get_token(self, token_id):
        # Get token entry from token id
        return self.__tokens.get(token_id)

    def get_token_by_sessionid(self, sessionid):
        # Get token from session id
        token_id = self.__sessionid_map.get(sessionid)
        if token_id is None:
            return None
        return self.get_token(token_id)

    def new(self, ttl):
        # Create a new token with given Time To Live
        token_id = str(uuid.uuid4())
        token = self.__tokens[token_id] = {
            'id': token_id,
            'added': int(time.time()),
            'last': int(time.time()),
            'ttl': ttl,
            'sessions': set(),
        }
        return token

    def add_session(self, sessionid, token):
        # Add a session id to the token object and session index
        self.__sessionid_map[sessionid] = token['id']
        token['sessions'].add(sessionid)

    def remove_session(self, sessionid):
        # Remove a session id from index and token object
        token_id = self.__sessionid_map.get(sessionid)
        if not token_id:
            return
        token = self.get_token(token_id)
        if not token:
            return
        if sessionid in token['sessions']:
            token['sessions'].remove(sessionid)

    def pop(self, token_id):
        # Remove a token from both indexes
        token = self.__tokens.pop(token_id)
        for sessionid in token['sessions']:
            self.__sessionid_map.pop(sessionid, None)


class AuthService(Service):

    def __init__(self, *args, **kwargs):
        super(AuthService, self).__init__(*args, **kwargs)
        self.authtokens = AuthTokens()

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
        return self.authtokens.new(ttl)['id']

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
        """Authenticate using a given `token` id."""

        def update_token(app, message):
            """
            On every new message from the registered connection
            make sure the token is still valid, updating last time or
            removing authentication
            """
            token = self.authtokens.get_token_by_sessionid(app.sessionid)
            if token is None:
                return
            if int(time.time()) - token['ttl'] < token['last']:
                token['last'] = int(time.time())
            else:
                self.authtokens.pop_token(token['id'])
                app.authenticated = False

        def remove_session(app):
            """
            On connection close, remove session id from token
            """
            self.authtokens.remove_session(app.sessionid)

        token = self.authtokens.get_token(token)
        if token is None:
            return False

        """
        If token exists and is still valid (TTL) do the following:
          - authenticate the connection
          - add the session id to token
          - register connection callbacks to update/remove token
        """
        if int(time.time()) - token['ttl'] < token['last']:
            token['last'] = int(time.time())
            self.authtokens.add_session(app.sessionid, token)
            app.register_callback('on_message', update_token)
            app.register_callback('on_close', remove_session)
            app.authenticated = True
            return True
        else:
            self.auth_tokens.pop_token(token)
            return False
