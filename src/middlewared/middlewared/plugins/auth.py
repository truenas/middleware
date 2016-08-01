import crypt

from middlewared.service import Service, no_auth_required


class AuthService(Service):

    @no_auth_required
    def login(self, username, password):
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
