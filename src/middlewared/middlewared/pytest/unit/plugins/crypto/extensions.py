import pytest

from middlewared.plugins.crypto_.generate_ca import generate_certificate_authority
from middlewared.plugins.crypto_.load_utils import load_certificate
from middlewared.plugins.crypto_.utils import DEFAULT_LIFETIME_DAYS


@pytest.mark.parametrize('generate_params,extension_info', [
    (
        {
            'key_type': 'RSA',
            'key_length': 4096,
            'san': ['domain1', '8.8.8.8'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'dev@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12931,
            'ca_certificate': None,
            'cert_extensions': {
                'BasicConstraints': {
                    'enabled': True,
                    'ca': True,
                    'extension_critical': True,
                },
            },
        },
        {'BasicConstraints': 'CA:TRUE'},
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 4096,
            'san': ['domain1', '8.8.8.8'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'dev@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12931,
            'ca_certificate': None,
            'cert_extensions': {
                'KeyUsage': {
                    'enabled': True,
                    'key_cert_sign': True,
                    'crl_sign': True,
                    'extension_critical': True,
                }
            },
        },
        {'KeyUsage': 'Certificate Sign, CRL Sign'},
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 4096,
            'san': ['domain1', '8.8.8.8'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'dev@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12931,
            'ca_certificate': None,
            'cert_extensions': {
                'KeyUsage': {
                    'enabled': True,
                    'key_cert_sign': True,
                    'crl_sign': False,
                    'extension_critical': True,
                }
            },
        },
        {'KeyUsage': 'Certificate Sign'},
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 4096,
            'san': ['domain1', '8.8.8.8'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'dev@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12931,
            'ca_certificate': None,
            'cert_extensions': {
                'ExtendedKeyUsage': {
                    'enabled': True,
                    'usages': [
                        'ANY_EXTENDED_KEY_USAGE', 'CLIENT_AUTH', 'CODE_SIGNING', 'EMAIL_PROTECTION',
                        'OCSP_SIGNING', 'SERVER_AUTH', 'TIME_STAMPING'
                    ],
                },
            },
        },
        {
            'ExtendedKeyUsage': 'Any Extended Key Usage, TLS Web Client Authentication, '
                                'Code Signing, E-mail Protection, OCSP Signing, TLS Web Server '
                                'Authentication, Time Stamping',
        },
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 4096,
            'san': ['domain1', '8.8.8.8'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'dev@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12931,
            'ca_certificate': None,
            'cert_extensions': {
                'KeyUsage': {
                    'enabled': True,
                    'digital_signature': True,
                    'content_commitment': True,
                    'key_encipherment': True,
                    'data_encipherment': True,
                    'key_agreement': True,
                },
            },
        },
        {
            'KeyUsage': 'Digital Signature, Non Repudiation, Key Encipherment, Data Encipherment, Key Agreement',
        },
    ),
])
def test__generating_ca(generate_params, extension_info):
    extensions = load_certificate(generate_certificate_authority(generate_params)[0], True)['extensions']
    for k in extension_info:
        assert k in extensions, extensions
        assert extensions[k] == extension_info[k]
