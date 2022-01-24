from cryptography import x509

from middlewared.schema import accepts, Ref, Str
from middlewared.service import Service, ValidationErrors

from .extensions_utils import add_extensions, get_extension_params


class CryptoKeyService(Service):

    class Config:
        private = True

    def add_extensions(self, cert, extensions_data, key, issuer=None):
        return add_extensions(cert, extensions_data, key, issuer)

    @accepts(
        Ref('cert_extensions'),
        Str('schema')
    )
    def validate_extensions(self, extensions_data, schema):
        # We do not need to validate some extensions like `AuthorityKeyIdentifier`.
        # They are generated from the cert/ca's public key contents. So we skip these.

        skip_extension = ['AuthorityKeyIdentifier']
        verrors = ValidationErrors()

        for extension in filter(lambda v: v[1]['enabled'] and v[0] not in skip_extension, extensions_data.items()):
            klass = getattr(x509.extensions, extension[0])
            try:
                klass(*get_extension_params(extension))
            except Exception as e:
                verrors.add(
                    f'{schema}.{extension[0]}',
                    f'Please provide valid values for {extension[0]}: {e}'
                )

        if extensions_data['KeyUsage']['enabled'] and extensions_data['KeyUsage']['key_cert_sign']:
            if not extensions_data['BasicConstraints']['enabled'] or not extensions_data['BasicConstraints']['ca']:
                verrors.add(
                    f'{schema}.BasicConstraints',
                    'Please enable ca when key_cert_sign is set in KeyUsage as per RFC 5280.'
                )

        if extensions_data['ExtendedKeyUsage']['enabled'] and not extensions_data['ExtendedKeyUsage']['usages']:
            verrors.add(
                f'{schema}.ExtendedKeyUsage.usages',
                'Please specify at least one USAGE for this extension.'
            )

        return verrors
