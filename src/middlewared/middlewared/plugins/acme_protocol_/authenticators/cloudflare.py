import logging

from certbot_dns_cloudflare._internal.dns_cloudflare import _CloudflareClient

from middlewared.schema import accepts, Dict, Str, ValidationErrors

from .base import Authenticator


logger = logging.getLogger(__name__)


class CloudFlareAuthenticator(Authenticator):

    NAME = 'cloudflare'
    PROPAGATION_DELAY = 60
    SCHEMA = Dict(
        'cloudflare',
        Str('cloudflare_email', empty=False, null=True, title='Cloudflare Email'),
        Str('api_key', empty=False, null=True, title='API Key'),
        Str('api_token', empty=False, null=True, title='API Token'),
    )

    def initialize_credentials(self):
        self.cloudflare_email = self.attributes.get('cloudflare_email')
        self.api_key = self.attributes.get('api_key')
        self.api_token = self.attributes.get('api_token')

    @staticmethod
    @accepts(SCHEMA)
    def validate_credentials(data):
        verrors = ValidationErrors()
        if data.get('api_token'):
            if data.get('cloudflare_email'):
                verrors.add('cloudflare_email', 'Should not be specified when using "api_token".')
            if data.get('api_key'):
                verrors.add('api_key', 'Should not be specified when using "api_token".')

        elif data.get('cloudflare_email') or data.get('api_key'):
            if not data.get('cloudflare_email'):
                verrors.add(
                    'cloudflare_email',
                    'Attribute is required when using a Global API Key (should be associated with Cloudflare account).'
                )
            if not data.get('api_key'):
                verrors.add('api_key', 'Attribute is required when using a Global API Key.')
        else:
            verrors.add('api_token', 'Attribute must be specified when Global API Key is not specified.')

        verrors.check()

    def _perform(self, domain, validation_name, validation_content):
        self.get_cloudflare_object().add_txt_record(domain, validation_name, validation_content, 600)

    def get_cloudflare_object(self):
        if self.api_token:
            params = (None, self.api_token)
        else:
            params = (self.cloudflare_email, self.api_key)
        return _CloudflareClient(*params)

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_cloudflare_object().del_txt_record(domain, validation_name, validation_content)
