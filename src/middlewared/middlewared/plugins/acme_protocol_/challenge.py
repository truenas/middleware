from typing import Any
import josepy as jose
import json

from acme import messages

from middlewared.api import api_method
from middlewared.api.base import BaseModel, single_argument_args, LongString
from middlewared.service import private, Service

from .authenticators.factory import auth_factory


@single_argument_args('acme_dns_authenticator_performance_challenge')
class ACMEDNSAuthenticatorPerformChallengeArgs(BaseModel):
    authenticator: Any
    key: LongString
    domain: str
    challenge: LongString


class ACMEDNSAuthenticatorPerformChallengeResult(BaseModel):
    result: None


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    @api_method(ACMEDNSAuthenticatorPerformChallengeArgs, ACMEDNSAuthenticatorPerformChallengeResult, private=True)
    def perform_challenge(self, data):
        authenticator = data['authenticator']
        authenticator.perform(*self.get_validation_parameters(data['challenge'], data['domain'], data['key']))

    @private
    def cleanup_challenge(self, data):
        authenticator = data['authenticator']
        authenticator.cleanup(*self.get_validation_parameters(data['challenge'], data['domain'], data['key']))

    @private
    def get_authenticator(self, authenticator):
        if authenticator is None:
            auth_details = {
                'attributes': {'authenticator': 'tn_connect', **self.middleware.call_sync('tn_connect.config_internal')}
            }
        else:
            auth_details = self.middleware.call_sync('acme.dns.authenticator.get_instance', authenticator)

        return self.get_authenticator_internal(
            auth_details['attributes']['authenticator']
        )(self.middleware, auth_details['attributes'])

    @private
    def get_authenticator_internal(self, authenticator_name):
        return auth_factory.authenticator(authenticator_name)

    @private
    def get_validation_parameters(self, challenge, domain, key):
        challenge = messages.ChallengeBody.from_json(json.loads(challenge))
        return (
            domain,
            challenge.validation_domain_name(domain),
            challenge.validation(jose.JWKRSA.fields_from_json(json.loads(key))),
        )
