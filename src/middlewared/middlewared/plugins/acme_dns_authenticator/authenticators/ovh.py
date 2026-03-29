import logging

from lexicon.client import Client
from lexicon.config import ConfigResolver

from middlewared.api.current import OVHSchemaArgs

from .base import Authenticator


logger = logging.getLogger(__name__)


class _OVHLexiconClient:
    """Compatibility wrapper for OVH Lexicon client to match the old certbot interface"""

    def __init__(self, endpoint, application_key, application_secret, consumer_key, ttl):
        self.endpoint = endpoint
        self.application_key = application_key
        self.application_secret = application_secret
        self.consumer_key = consumer_key
        self.ttl = ttl

    def add_txt_record(self, domain, validation_name, validation_content):
        """Add a TXT record using the OVH API via Lexicon"""
        config = ConfigResolver().with_dict({
            'provider_name': 'ovh',
            'domain': domain,
            'delegated': domain,  # Bypass Lexicon subdomain resolution
            'ttl': self.ttl,
            'ovh': {
                'auth_entrypoint': self.endpoint,
                'auth_application_key': self.application_key,
                'auth_application_secret': self.application_secret,
                'auth_consumer_key': self.consumer_key
            }
        })

        with Client(config) as operations:
            operations.create_record(rtype='TXT', name=validation_name, content=validation_content)

    def del_txt_record(self, domain, validation_name, validation_content):
        """Delete a TXT record using the OVH API via Lexicon"""
        config = ConfigResolver().with_dict({
            'provider_name': 'ovh',
            'domain': domain,
            'delegated': domain,  # Bypass Lexicon subdomain resolution
            'ttl': self.ttl,
            'ovh': {
                'auth_entrypoint': self.endpoint,
                'auth_application_key': self.application_key,
                'auth_application_secret': self.application_secret,
                'auth_consumer_key': self.consumer_key
            }
        })

        with Client(config) as operations:
            operations.delete_record(rtype='TXT', name=validation_name, content=validation_content)


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
