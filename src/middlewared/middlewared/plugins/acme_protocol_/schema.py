from middlewared.service import accepts, private, Service

from .authenticators.factory import auth_factory


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    def __init__(self, *args, **kwargs):
        super(DNSAuthenticatorService, self).__init__(*args, **kwargs)
        self.schemas = self.get_authenticator_schemas()

    @accepts()
    def authenticator_schemas(self):
        """
        Get the schemas for all DNS providers we support for ACME DNS Challenge and the respective attributes
        required for connecting to them while validating a DNS Challenge
        """
        return [
            {'schema': [v.to_json_schema() for v in value.attrs.values()], 'key': key}
            for key, value in self.schemas.items()
        ]

    @private
    def get_authenticator_schemas(self):
        return {k: klass.SCHEMA for k, klass in auth_factory.get_authenticators().items()}
