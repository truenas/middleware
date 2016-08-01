import crypt

from middlewared.service import Service, no_auth_required, pass_app


class AuthService(Service):

    @no_auth_required
    @pass_app
    def login(self, app, username, password):
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
        valid = crypt.crypt(password, user['bsdusr_unixhash']) == user['bsdusr_unixhash']
        if valid:
            app.authenticated = True
        return valid
