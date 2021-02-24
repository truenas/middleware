import errno

from middlewared.service_exception import CallError


class AuthenticatorFactory:

    def __init__(self):
        self._creators = {}

    def register(self, authenticator):
        self._creators[authenticator.NAME] = authenticator

    def authenticator(self, name):
        if name not in self._creators:
            raise CallError(f'Unable to locate {name!r} authenticator.', errno=errno.ENOENT)
        return self._creators[name]


auth_factory = AuthenticatorFactory()
