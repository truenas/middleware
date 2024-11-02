import logging

from certbot_dns_cloudflare._internal.dns_cloudflare import _CloudflareClient

from middlewared.api import api_method
from middlewared.api.current import CloudFlareSchemaArgs, ACMECustomDNSAuthenticatorReturns
from middlewared.schema import accepts, Dict, Password, Str, ValidationErrors
from middlewared.service import skip_arg

from .base import Authenticator


logger = logging.getLogger(__name__)


class CloudFlareAuthenticator(Authenticator):

    NAME = 'cloudflare'
    PROPAGATION_DELAY = 60
    SCHEMA = Dict(
        'cloudflare',
        Str('cloudflare_email', empty=False, null=True, title='Cloudflare Email'),
        Password('api_key', empty=False, null=True, title='API Key'),
        Password('api_token', empty=False, null=True, title='API Token'),
    )
    SCHEMA_MODEL = CloudFlareSchemaArgs

    def initialize_credentials(self):
        self.cloudflare_email = self.attributes.get('cloudflare_email')
        self.api_key = self.attributes.get('api_key')
        self.api_token = self.attributes.get('api_token')

    @staticmethod
    @api_method(CloudFlareSchemaArgs, ACMECustomDNSAuthenticatorReturns)
    @skip_arg(count=1)
    async def validate_credentials(middleware, data):
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
        return data

    def _perform(self, domain, validation_name, validation_content):
        self.get_cloudflare_object().add_txt_record(domain, validation_name, validation_content, 600)

    def get_cloudflare_object(self):
        if self.api_token:
            return _CloudflareClient(api_token=self.api_token)
        else:
            return _CloudflareClient(email=self.cloudflare_email, api_key=self.api_key)

    def _cleanup(self, domain, validation_name, validation_content):
        self.get_cloudflare_object().del_txt_record(domain, validation_name, validation_content)
