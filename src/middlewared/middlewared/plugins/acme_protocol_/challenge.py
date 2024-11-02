import josepy as jose
import json

from acme import messages

from middlewared.api import api_method
from middlewared.api.current import ACMEDNSAuthenticatorPerformChallengeArgs, ACMEDNSAuthenticatorPerformChallengeResult
from middlewared.service import private, Service

from .authenticators.factory import auth_factory


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    @api_method(ACMEDNSAuthenticatorPerformChallengeArgs, ACMEDNSAuthenticatorPerformChallengeResult, private=True)
    def perform_challenge(self, data):
        authenticator = self.get_authenticator(data['authenticator'])
        authenticator.perform(*self.get_validation_parameters(data['challenge'], data['domain'], data['key']))

    @private
    def cleanup_challenge(self, data):
        authenticator = self.get_authenticator(data['authenticator'])
        authenticator.cleanup(*self.get_validation_parameters(data['challenge'], data['domain'], data['key']))

    @private
    def get_authenticator(self, authenticator):
        auth_details = self.middleware.call_sync('acme.dns.authenticator.get_instance', authenticator)
        return self.get_authenticator_internal(auth_details)(self.middleware, auth_details['attributes'])

    @private
    def get_authenticator_internal(self, auth_details):
        return auth_factory.authenticator(auth_details['authenticator'])

    @private
    def get_validation_parameters(self, challenge, domain, key):
        challenge = messages.ChallengeBody.from_json(json.loads(challenge))
        return (
            domain,
            challenge.validation_domain_name(domain),
            challenge.validation(jose.JWKRSA.fields_from_json(json.loads(key))),
        )
