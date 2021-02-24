from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import private, Service

from .authenticators.factory import auth_factory


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    @accepts(
        Dict(
            'perform_challenge',
            Int('authenticator', required=True),
            Str('key', required=True, max_length=None),
            Str('domain', required=True),
            Str('challenge', required=True, max_length=None),
        )
    )
    @private
    def perform_challenge(self, data):
        auth_details = self.middleware.call_sync('acme.dns.authenticator.get_instance', data['authenticator'])
        authenticator = auth_factory.authenticator(auth_details['authenticator'].lower())(auth_details['attributes'])
        authenticator.perform()
