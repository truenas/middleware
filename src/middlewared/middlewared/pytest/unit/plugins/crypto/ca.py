import pytest
import textwrap

from cryptography.hazmat.primitives.asymmetric import rsa

from middlewared.plugins.crypto_.generate_ca import generate_certificate_authority
from middlewared.plugins.crypto_.load_utils import load_certificate, load_private_key
from middlewared.plugins.crypto_.utils import DEFAULT_LIFETIME_DAYS


@pytest.mark.parametrize('generate_params,key_type,key_size,ca_info', [
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
                'AuthorityKeyIdentifier': {
                    'enabled': False,
                },
                'ExtendedKeyUsage': {
                    'enabled': True,
                    'usages': ['SERVER_AUTH'],
                },
                'KeyUsage': {
                    'enabled': True,
                    'key_cert_sign': True,
                    'crl_sign': True,
                    'extension_critical': True,
                }
            },
        },
        rsa.RSAPrivateKey, 4096,
        {
            'DN': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=dev@ix.com/subjectAlt'
                  'Name=DNS:domain1, IP Address:8.8.8.8',
            'chain': False,
            'city': 'Knoxville',
            'common': 'dev',
            'country': 'US',
            'digest_algorithm': 'SHA256',
            'email': 'dev@ix.com',
            'extensions': {
                'SubjectAltName': 'DNS:domain1, IP Address:8.8.8.8',
                'BasicConstraints': 'CA:TRUE',
                'ExtendedKeyUsage': 'TLS Web Server Authentication',
                'KeyUsage': 'Certificate Sign, CRL Sign',
            },
            'fingerprint': '45:43:04:3D:73:3D:01:CD:98:E9:63:93:8C:61:DC:2F:68:ED:E3:77',
            'from': 'Mon Jan 24 10:20:50 2022',
            'issuer_dn': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=dev@ix.com',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'organization': 'iX',
            'organizational_unit': 'dev',
            'san': ['DNS:domain1', 'IP Address:8.8.8.8'],
            'serial': 12931,
            'state': 'TN',
            'subject_name_hash': 877114495,
            'until': 'Sat Feb 25 10:20:50 2023'
        },
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 4096,
            'san': ['domain2', '9.9.9.9'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'iamchild@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12934,
            'ca_certificate': textwrap.dedent('''\
                -----BEGIN CERTIFICATE-----
                MIIFmzCCA4OgAwIBAgICMoMwDQYJKoZIhvcNAQELBQAwcjEMMAoGA1UEAwwDZGV2
                MQswCQYDVQQGEwJVUzELMAkGA1UECAwCVE4xEjAQBgNVBAcMCUtub3h2aWxsZTEL
                MAkGA1UECgwCaVgxDDAKBgNVBAsMA2RldjEZMBcGCSqGSIb3DQEJARYKZGV2QGl4
                LmNvbTAeFw0yMjAxMjQxOTI0MTRaFw0yMzAyMjUxOTI0MTRaMHIxDDAKBgNVBAMM
                A2RldjELMAkGA1UEBhMCVVMxCzAJBgNVBAgMAlROMRIwEAYDVQQHDAlLbm94dmls
                bGUxCzAJBgNVBAoMAmlYMQwwCgYDVQQLDANkZXYxGTAXBgkqhkiG9w0BCQEWCmRl
                dkBpeC5jb20wggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQDuy5kKf7eT
                LOuxm1pn51kFLgJHD6k05pROjMOXEZel7CsmrDKEehSSdwDB/WUim3idOsImLrc+
                ApXsnKwVY93f7yn1rfF4lgKsa3sb6oqAcPEobgTUqSmJ/OQVilUqOtj/dmFaEWIS
                21eKNzaByNdpyOcoRF/+uDylEsE1Gj0GjkBneVRxyTZFV7LdVyDk38hljesnd8FX
                gnD0DCdI3jBvqSYvd+GvQ2nQ2624HAmEQwfllqKi9PRDngeZIeiTQSWN+rybJbDY
                yonRS0FPxJydt/sDlzi43qzHnrTqUbL+2RjYIqcOqeivNtDZ2joh+xqfRdKzACWu
                QWrhGCL5+9bnqA6PEPA7GQ2jp00gDkjB7+HlQLI8ZCZcST6mkbfs/EaW00WYIcw5
                lb+5oJ8oJqWebnQB21iwvPjvAv353iA1ApTJxBdo13x7oXBwWsrpxWk6SdL2Z5zU
                NXrC9ZyaoeQ5uZ/oBXbCxJfhSkISyI5D8yeYLjmMxn+AvRBQpkRmVvcy3ls2SHGX
                4XEJ4Q0wj3a0rPqmDZUwpWErbmf+N6D7J+uK8n3pcGlvkFIUaP60UQGp4gwnZA2O
                dZdhVQ4whQHyjTmL7kRKl+gR/vTp+iPvKMfTO1HBQp97iK8IPM7Q2Gpe6U4n/Ll2
                TDaZ9DroM83Vnc6cX69Th555SA9+gP6HWQIDAQABozswOTAYBgNVHREEETAPggdk
                b21haW4xhwQICAgIMB0GA1UdDgQWBBSz0br/9U9mwYZfuRO1JmKTEorq1DANBgkq
                hkiG9w0BAQsFAAOCAgEAK7nBNA+qjgvkmcSLQC+yXPOwb3o55D+N0J2QLxJFT4NV
                b0GKf0dkz92Ew1pkKYzsH6lLlKRE23cye6EZLIwkkhhF0sTwYeu8HNy7VmkSDsp0
                aKbqxgBzIJx+ztQGNgZ1fQMRjHCRLf8TaSAxnVXaXXUeU6fUBq2gHbYq6BfZkGmU
                6f8DzL7uKHzcMEmWfC5KxfSskFFPOyaz/VGViQ0yffwH1NB+txDlU58rmu9w0wLe
                cOrOjVUNg8axQen2Uejjj3IRmDC18ZfY7EqI8O1PizCtIcPSm+NnZYg/FvVj0KmM
                o2QwGMd5QTU2J5lz988Xlofm/r3GBH32+ETqIcJolBw9bBkwruBvHpcmyLSFcFWK
                sdGgi2gK2rGb+oKwzpHSeCtQVwgQth55qRH1DQGaAdpA1uTriOdcR96i65/jcz96
                aD2B958hF1B/7I4Md+LFYhxgwREBhyQkU6saf7GR0Q+p4F8/oIkjhdLsyzk4YHyI
                PVtK00W8zQMKF6zhHjfaF2uDRO/ycMKCq9NIqQJCZNqwNAo0r4FOmilwud/tzFY8
                GQ9FXeQSqWo7hUIXdbej+aJ7DusYeuE/CwQFNUnz1khvIFJ5B7YP+gYCyUW7V2Hr
                Mv+cZ473U8hYQ1Ij7pXi7DxsOWqWCDhyK0Yp6MZsw0rNaAIPHnTTxYdMfmIYHT0=
                -----END CERTIFICATE-----
            '''),
            'cert_extensions': {
                'BasicConstraints': {
                    'enabled': True,
                    'ca': True,
                    'extension_critical': True,
                },
                'AuthorityKeyIdentifier': {
                    'enabled': False,
                },
                'ExtendedKeyUsage': {
                    'enabled': True,
                    'usages': ['SERVER_AUTH'],
                },
                'KeyUsage': {
                    'enabled': True,
                    'key_cert_sign': True,
                    'crl_sign': True,
                    'extension_critical': True,
                }
            },
        }, rsa.RSAPrivateKey, 4096,
        {
            'DN': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=iamchild@ix.com/'
                  'subjectAltName=DNS:domain2, IP Address:9.9.9.9',
            'chain': False,
            'city': 'Knoxville',
            'common': 'dev',
            'country': 'US',
            'digest_algorithm': 'SHA256',
            'email': 'iamchild@ix.com',
            'extensions': {
                'SubjectAltName': 'DNS:domain2, IP Address:9.9.9.9',
                'BasicConstraints': 'CA:TRUE',
                'ExtendedKeyUsage': 'TLS Web Server Authentication',
                'KeyUsage': 'Certificate Sign, CRL Sign',
            },
            'fingerprint': '5C:BF:5A:CF:76:12:48:1B:85:A0:AE:2C:5D:E0:51:85:B3:C2:40:79',
            'from': 'Mon Jan 24 11:28:07 2022',
            'issuer_dn': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=dev@ix.com',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'organization': 'iX',
            'organizational_unit': 'dev',
            'san': ['DNS:domain2', 'IP Address:9.9.9.9'],
            'serial': 12934,
            'state': 'TN',
            'subject_name_hash': 3214950212,
            'until': 'Sat Feb 25 11:28:07 2023'
        }
    )
])
def test__generating_ca(generate_params, key_type, key_size, ca_info):
    ca_str, key = generate_certificate_authority(generate_params)
    ca_details = load_certificate(ca_str, True)
    key_obj = load_private_key(key)
    assert isinstance(key_obj, rsa.RSAPrivateKey) is True
    assert key_obj.key_size == key_size

    # there are certain keys which are special and we should not be validating those as they would differ
    special_props = ['fingerprint', 'from', 'until', 'subject_name_hash']
    for k in ca_info:
        assert k in ca_details, ca_details

        if k in special_props:
            continue
        if k == 'extensions':
            assert 'SubjectKeyIdentifier' in ca_details[k], ca_details[k]
            ca_details[k].pop('SubjectKeyIdentifier')

        assert ca_info[k] == ca_details[k], ca_details
