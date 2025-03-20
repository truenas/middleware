from cryptography import x509

from truenas_crypto_utils.extensions import get_extension_params

from middlewared.service import Service, ValidationErrors


class CryptoKeyService(Service):

    class Config:
        private = True

    def validate_extensions(self, extensions_data, schema):
        verrors = ValidationErrors()

        for extension in filter(lambda v: v[1]['enabled'], extensions_data.items()):
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
