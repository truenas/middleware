import logging

from certbot_dns_ovh._internal.dns_ovh import _OVHLexiconClient

from middlewared.api.current import OVHSchemaArgs

from .base import Authenticator


logger = logging.getLogger(__name__)


class OVHAuthenticator(Authenticator):

    NAME = 'OVH'
    PROPAGATION_DELAY = 60
    SCHEMA_MODEL = OVHSchemaArgs

    def initialize_credentials(self):
        self.application_key = self.attributes.get('application_key')
        self.application_secret = self.attributes.get('application_secret')
        self.consumer_key = self.attributes.get('consumer_key')
        self.endpoint = self.attributes.get('endpoint')

    @staticmethod
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
