import typing

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization

from .generate_utils import generate_builder, normalize_san
from .key_utils import generate_private_key
from .utils import DEFAULT_LIFETIME_DAYS


def generate_self_signed_certificate() -> typing.Tuple[str, str]:
    cert = generate_builder({
        'crypto_subject_name': {
            'country_name': 'US',
            'organization_name': 'iXsystems',
            'common_name': 'localhost',
            'email_address': 'info@ixsystems.com',
            'state_or_province_name': 'Tennessee',
            'locality_name': 'Maryville',
        },
        'lifetime': DEFAULT_LIFETIME_DAYS,
        'san': normalize_san(['localhost'])
    })
    key = generate_private_key({
        'serialize': False,
        'key_length': 2048,
        'type': 'RSA'
    })

    cert = cert.public_key(
        key.public_key()
    ).add_extension(
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False
    ).sign(
        key, hashes.SHA256(), default_backend()
    )

    return (
        cert.public_bytes(serialization.Encoding.PEM).decode(),
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
    )
