import errno

from middlewared.service_exception import CallError

from .cloudflare import CloudFlareAuthenticator
from .ovh import OVHAuthenticator
from .route53 import Route53Authenticator
from .shell import ShellAuthenticator
from .truenas_connect import TrueNASConnectAuthenticator


class AuthenticatorFactory:

    def __init__(self):
        self._creators = {}

    def register(self, authenticator):
        self._creators[authenticator.NAME] = authenticator

    def authenticator(self, name):
        if name not in self._creators:
            raise CallError(f'Unable to locate {name!r} authenticator.', errno=errno.ENOENT)
        return self._creators[name]

    def get_authenticators(self, include_internal=False):
        return {k: v for k, v in self._creators.items() if v.INTERNAL is False or include_internal}


auth_factory = AuthenticatorFactory()
for authenticator in [
    CloudFlareAuthenticator,
    Route53Authenticator,
    OVHAuthenticator,
    ShellAuthenticator,
    TrueNASConnectAuthenticator,
]:
    auth_factory.register(authenticator)
