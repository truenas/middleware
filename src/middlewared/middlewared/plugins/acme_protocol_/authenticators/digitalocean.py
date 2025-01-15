import logging

from certbot_dns_digitalocean._internal.dns_digitalocean import _DigitalOceanClient

from middlewared.api.current import DigitalOceanSchemaArgs

from .base import Authenticator


logger = logging.getLogger(__name__)


class DigitalOceanAuthenticator(Authenticator):

    NAME = 'digitalocean'
    PROPAGATION_DELAY = 60
    SCHEMA_MODEL = DigitalOceanSchemaArgs

    def initialize_credentials(self):
        self.digitalocean_token = self.attributes.get('digitalocean_token')

    @staticmethod
    async def validate_credentials(middleware, data):
        return data

    def _perform(self, domain, validation_name, validation_content):
        self.get_client().add_txt_record(domain, validation_name, validation_content, 600)

    def get_client(self):
        return _DigitalOceanClient(self.digitalocean_token)

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_client().del_txt_record(domain, validation_name, validation_content)
