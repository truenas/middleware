

import logging

from certbot_dns_google._internal.dns_google import _GoogleClient

from middlewared.schema import accepts, Dict, File
from middlewared.service import skip_arg

from .base import Authenticator


logger = logging.getLogger(__name__)


class GoogleAuthenticator(Authenticator):

    NAME = 'Google DNS'
    PROPAGATION_DELAY = 60
    SCHEMA = Dict(
        'Google',
        File('service_account_path', empty=False, null=False, title='Path to the service account JSON', required=True),
    )

    def initialize_credentials(self):
        self.service_account = self.attributes.get('service_account_path')

    @staticmethod
    @accepts(SCHEMA)
    @skip_arg(count=1)
    async def validate_credentials(middleware, data):
        return data

    def _perform(self, domain, validation_name, validation_content):
        self.get_client().add_txt_record(domain, validation_name, validation_content, 600)

    def get_client(self):
        return _GoogleClient(self.service_account)

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_client().del_txt_record(domain, validation_name, validation_content, 600)
