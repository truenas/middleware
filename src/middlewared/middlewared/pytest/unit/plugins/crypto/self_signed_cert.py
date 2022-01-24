from cryptography.hazmat.primitives.asymmetric import rsa

from middlewared.plugins.crypto_.generate_self_signed import DEFAULT_LIFETIME_DAYS, generate_self_signed_certificate
from middlewared.plugins.crypto_.load_utils import load_certificate, load_private_key


SELF_SIGNED_CERT = {
    'country': 'US',
    'state': 'Tennessee',
    'city': 'Maryville',
    'organization': 'iXsystems',
    'organizational_unit': None,
    'common': 'localhost',
    'san': ['DNS:localhost'],
    'email': 'info@ixsystems.com',
    'DN': '/C=US/O=iXsystems/CN=localhost/emailAddress=info@ixsystems.com/ST=Tennessee/'
          'L=Maryville/subjectAltName=DNS:localhost',
    'extensions': {'SubjectAltName': 'DNS:localhost', 'ExtendedKeyUsage': 'TLS Web Server Authentication'},
    'digest_algorithm': 'SHA256',
    'lifetime': DEFAULT_LIFETIME_DAYS,
    'chain': False,
}


def test__generating_self_signed_cert():
    cert, key = generate_self_signed_certificate()
    cert_info = load_certificate(cert)
    key_obj = load_private_key(key)
    for k, v in SELF_SIGNED_CERT.items():
        assert k in cert_info, cert_info
        assert v == cert_info[k], cert_info

    assert isinstance(key_obj, rsa.RSAPrivateKey), f'Private key has different type {key!r}'
