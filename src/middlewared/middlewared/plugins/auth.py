import crypt

from middlewared.schema import Str, accepts
from middlewared.service import Service, no_auth_required, pass_app


class AuthService(Service):

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

    @no_auth_required
    @accepts(Str('username'), Str('password'))
    @pass_app
    def login(self, app, username, password):
        valid = self.check_user(username, password)
        if valid:
            app.authenticated = True
        return valid
