import inspect

from cryptography import x509

from middlewared.schema import accepts, Ref, Str
from middlewared.service import Service, ValidationErrors


class CryptoKeyService(Service):

    EXTENSIONS = {}

    class Config:
        private = True

    @staticmethod
    def extensions():
        if not CryptoKeyService.EXTENSIONS:
            # For now we only support the following extensions
            # We also support SubjectAlternativeName but as we include that natively if the user provides it
            # we don't expose it to the end user as an extension making the process for the end user easier to
            # create a certificate/ca as most wouldn't even want to know what extension is or does.
            # Apart from this we also add subjectKeyIdentifier automatically
            supported = ['BasicConstraints', 'AuthorityKeyIdentifier', 'ExtendedKeyUsage', 'KeyUsage']

            for attr in supported:
                attr_obj = getattr(x509.extensions, attr)
                CryptoKeyService.EXTENSIONS[attr] = inspect.getfullargspec(attr_obj.__init__).args[1:]

        return CryptoKeyService.EXTENSIONS

    def add_extensions(self, cert, extensions_data, key, issuer=None):
        # issuer must be a certificate object
        # By default we add the following
        if not isinstance(cert, x509.CertificateSigningRequestBuilder):
            cert = cert.public_key(
                key.public_key()
            ).add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False
            )

        for extension in filter(lambda v: v[1]['enabled'], extensions_data.items()):
            klass = getattr(x509.extensions, extension[0])
            cert = cert.add_extension(
                klass(*self.get_extension_params(extension, cert, issuer)),
                extension[1].get('extension_critical') or False
            )

        return cert

    def get_extension_params(self, extension, cert=None, issuer=None):
        params = []

        if extension[0] == 'BasicConstraints':
            params = [extension[1].get('ca'), extension[1].get('path_length')]
        elif extension[0] == 'ExtendedKeyUsage':
            usages = []
            for ext_usage in extension[1].get('usages', []):
                usages.append(getattr(x509.oid.ExtendedKeyUsageOID, ext_usage))
            params = [usages]
        elif extension[0] == 'KeyUsage':
            params = [extension[1].get(k, False) for k in self.extensions()['KeyUsage']]
        elif extension[0] == 'AuthorityKeyIdentifier':
            params = [
                x509.SubjectKeyIdentifier.from_public_key(
                    issuer.public_key() if issuer else cert._public_key
                ).digest if cert or issuer else None,
                None, None
            ]

            if extension[1]['authority_cert_issuer'] and cert:
                params[1:] = [
                    [x509.DirectoryName(cert._issuer_name)],
                    issuer.serial_number if issuer else cert._serial_number
                ]

        return params

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
                klass(*self.get_extension_params(extension))
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
