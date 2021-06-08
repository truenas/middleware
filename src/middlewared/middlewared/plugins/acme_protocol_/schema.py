from middlewared.schema import Bool, Dict, Str, List, returns
from middlewared.service import accepts, private, Service

from .authenticators.factory import auth_factory


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    def __init__(self, *args, **kwargs):
        super(DNSAuthenticatorService, self).__init__(*args, **kwargs)
        self.schemas = self.get_authenticator_schemas()

    @accepts()
    @returns(List(
        title='Authenticator Schemas',
        items=[Dict(
            'schema_entry',
            Str('key', required=True),
            List(
                'schema',
                items=[Dict(
                    'attribute_schema',
                    Str('_name_', required=True),
                    Str('title', required=True),
                    Bool('_required_', required=True),
                    additional_attrs=True,
                    title='Attribute Schema',
                )],
            ),
            title='Authenticator Schema'
        )],
    ))
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
