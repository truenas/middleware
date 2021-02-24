import logging

from certbot_dns_cloudflare._internal.dns_cloudflare import _CloudflareClient

from .base import Authenticator
from .factory import auth_factory


logger = logging.getLogger(__name__)


class CloudFlareAuthenticator(Authenticator):

    NAME = 'cloudflare'

    def initialize_credentials(self):
        self.cloudflare_email = self.attributes['cloudflare_email']
        self.api_key = self.attributes['api_key']

    def _validate_credentials(self, verrors):
        for k in ('cloudflare_email', 'domain', 'api_key'):
            if not getattr(self, k, None):
                verrors.add(k, 'Please provide a valid value.')

    def _perform(self, domain, validation_name, validation_content):
        self.get_cloudflare_object().add_txt_record(domain, validation_name, validation_content, 3600)

    def get_cloudflare_object(self):
        return _CloudflareClient(self.cloudflare_email, self.api_key)

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_cloudflare_object().del_txt_record(domain, validation_name, validation_content)


auth_factory.register(CloudFlareAuthenticator)
