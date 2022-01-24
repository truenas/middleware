import functools
import inspect
import typing

from cryptography import x509


@functools.cache
def extensions() -> dict:
    # For now we only support the following extensions
    # We also support SubjectAlternativeName but as we include that natively if the user provides it
    # we don't expose it to the end user as an extension making the process for the end user easier to
    # create a certificate/ca as most wouldn't even want to know what extension is or does.
    # Apart from this we also add subjectKeyIdentifier automatically
    supported = ['BasicConstraints', 'AuthorityKeyIdentifier', 'ExtendedKeyUsage', 'KeyUsage']

    return {
        attr: inspect.getfullargspec(getattr(x509.extensions, attr).__init__).args[1:]
        for attr in supported
    }


def get_extension_params(
    extension: list, cert: typing.Union[x509.CertificateSigningRequestBuilder, x509.CertificateBuilder, None] = None,
    issuer: typing.Optional[x509.Certificate] = None
) -> list:
    params = []

    if extension[0] == 'BasicConstraints':
        params = [extension[1].get('ca'), extension[1].get('path_length')]
    elif extension[0] == 'ExtendedKeyUsage':
        usages = []
        for ext_usage in extension[1].get('usages', []):
            usages.append(getattr(x509.oid.ExtendedKeyUsageOID, ext_usage))
        params = [usages]
    elif extension[0] == 'KeyUsage':
        params = [extension[1].get(k, False) for k in extensions()['KeyUsage']]
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


def add_extensions(
    cert: typing.Union[x509.CertificateSigningRequestBuilder, x509.CertificateBuilder], extensions_data: dict,
    key, issuer=None
) -> typing.Union[x509.CertificateSigningRequestBuilder, x509.CertificateBuilder]:
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
            klass(*get_extension_params(extension, cert, issuer)),
            extension[1].get('extension_critical') or False
        )

    return cert
