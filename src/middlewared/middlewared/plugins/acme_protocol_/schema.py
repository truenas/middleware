from middlewared.api import api_method
from middlewared.api.base.jsonschema import get_json_schema
from middlewared.api.current import DNSAuthenticatorAuthenticatorSchemasArgs, DNSAuthenticatorAuthenticatorSchemasResult
from middlewared.service import private, Service

from .authenticators.factory import auth_factory


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    def __init__(self, *args, **kwargs):
        super(DNSAuthenticatorService, self).__init__(*args, **kwargs)
        self.schemas = self.get_authenticator_schemas()

    @api_method(DNSAuthenticatorAuthenticatorSchemasArgs, DNSAuthenticatorAuthenticatorSchemasResult, roles=['READONLY_ADMIN'])
    def authenticator_schemas(self):
        """
        Get the schemas for all DNS providers we support for ACME DNS Challenge and the respective attributes
        required for connecting to them while validating a DNS Challenge
        """
        return [
            {'schema': get_json_schema(model)[0], 'key': key}
            for key, model in self.schemas.items()
        ]

    @private
    def get_authenticator_schemas(self):
        return {k: klass.SCHEMA_MODEL for k, klass in auth_factory.get_authenticators().items()}
