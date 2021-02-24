import errno

from middlewared.service_exception import CallError

from .cloudflare import CloudFlareAuthenticator
from .route53 import Route53Authenticator


class AuthenticatorFactory:

    def __init__(self):
        self._creators = {}

    def register(self, authenticator):
        self._creators[authenticator.NAME] = authenticator

    def authenticator(self, name):
        if name not in self._creators:
            raise CallError(f'Unable to locate {name!r} authenticator.', errno=errno.ENOENT)
        return self._creators[name]

    def get_authenticators(self):
        return self._creators


auth_factory = AuthenticatorFactory()
for authenticator in [
    CloudFlareAuthenticator,
    Route53Authenticator,
]:
    auth_factory.register(authenticator)
