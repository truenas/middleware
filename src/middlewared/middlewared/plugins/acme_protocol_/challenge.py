from middlewared.service import private, Service

from .authenticators.factory import auth_factory


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    @private
    def get_authenticator_internal(self, authenticator_name):
        return auth_factory.authenticator(authenticator_name)
