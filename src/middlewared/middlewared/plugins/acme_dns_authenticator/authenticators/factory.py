from __future__ import annotations

import errno

from middlewared.service_exception import CallError

from .base import Authenticator
from .cloudflare import CloudFlareAuthenticator
from .digitalocean import DigitalOceanAuthenticator
from .ovh import OVHAuthenticator
from .route53 import Route53Authenticator
from .shell import ShellAuthenticator


class AuthenticatorFactory:

    def __init__(self) -> None:
        self._creators: dict[str, type[Authenticator]] = {}

    def register(self, authenticator: type[Authenticator]) -> None:
        self._creators[authenticator.NAME] = authenticator

    def authenticator(self, name: str) -> type[Authenticator]:
        if name not in self._creators:
            raise CallError(f"Unable to locate {name!r} authenticator.", errno=errno.ENOENT)
        return self._creators[name]

    def get_authenticators(self, include_internal: bool = False) -> dict[str, type[Authenticator]]:
        return {k: v for k, v in self._creators.items() if v.INTERNAL is False or include_internal}


auth_factory = AuthenticatorFactory()
for authenticator in [
    CloudFlareAuthenticator,
    DigitalOceanAuthenticator,
    Route53Authenticator,
    OVHAuthenticator,
    ShellAuthenticator,
]:
    auth_factory.register(authenticator)
