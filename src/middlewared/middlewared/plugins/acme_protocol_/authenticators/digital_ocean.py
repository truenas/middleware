import logging

from certbot_dns_digitalocean._internal.dns_digitalocean import _DigitalOceanClient

from middlewared.schema import accepts, Dict, Str
from middlewared.service import skip_arg

from .base import Authenticator


logger = logging.getLogger(__name__)


class DigitalOceanAuthenticator(Authenticator):

    NAME = 'Digital Ocean'
    PROPAGATION_DELAY = 60
    SCHEMA = Dict(
        'Digital Ocean',
        Str('api_token', empty=False, null=False, title='API Token', required=True),
    )

    def initialize_credentials(self):
        self.api_token = self.attributes.get('api_token')

    @staticmethod
    @accepts(SCHEMA)
    @skip_arg(count=1)
    async def validate_credentials(middleware, data):
        return data

    def _perform(self, domain, validation_name, validation_content):
        self.get_client().add_txt_record(domain, validation_name, validation_content, 600)

    def get_client(self):
        return _DigitalOceanClient(self.api_token)

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_client().del_txt_record(domain, validation_name, validation_content, 600)
