import logging

from lexicon.providers.ovh import ENDPOINTS
from certbot_dns_ovh._internal.dns_ovh import _OVHLexiconClient

from middlewared.schema import accepts, Dict, Str
from middlewared.service import skip_arg

from .base import Authenticator


logger = logging.getLogger(__name__)
OVH_ENDPOINTS = tuple(ENDPOINTS.keys())

class OVHAuthenticator(Authenticator):

    NAME = 'OVH'
    PROPAGATION_DELAY = 60
    SCHEMA = Dict(
        'OVH',
        Str('application_key', empty=False, null=False, title='OVH Application Key', required=True),
        Str('application_secret', empty=False, null=False, title='OVH Application Secret', required=True),
        Str('consumer_key', empty=False, null=False, title='OVH Consumer Key', required=True),
        Str('endpoint', empty=False, default='ovh-eu', title='OVH Endpoint', enum=OVH_ENDPOINTS, required=True),
    )

    def initialize_credentials(self):
        self.application_key = self.attributes.get('application_key')
        self.application_secret = self.attributes.get('application_secret')
        self.consumer_key = self.attributes.get('consumer_key')
        self.endpoint = self.attributes.get('endpoint')

    @staticmethod
    @accepts(SCHEMA)
    @skip_arg(count=1)
    async def validate_credentials(middleware, data):
        return data

    def _perform(self, domain, validation_name, validation_content):
        self.get_client().add_txt_record(domain, validation_name, validation_content)

    def get_client(self):
        return _OVHLexiconClient(
            self.endpoint, self.application_key, self.application_secret,
            self.consumer_key, 600,
        )

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_client().del_txt_record(domain, validation_name, validation_content)
