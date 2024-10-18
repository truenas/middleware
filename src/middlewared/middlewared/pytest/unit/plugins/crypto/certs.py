import textwrap

import pytest

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from middlewared.plugins.crypto_.generate_certs import generate_certificate
from middlewared.plugins.crypto_.generate_utils import sign_csr_with_ca
from middlewared.plugins.crypto_.load_utils import load_certificate, load_private_key
from middlewared.plugins.crypto_.utils import DEFAULT_LIFETIME_DAYS


@pytest.mark.parametrize('generate_params,key_type,key_size,cert_info', [
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
                    'enabled': False,
                },
                'AuthorityKeyIdentifier': {
                    'enabled': False,
                },
                'ExtendedKeyUsage': {
                    'enabled': False,
                },
                'KeyUsage': {
                    'enabled': False,
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
    ),
    (
        {
            'key_type': 'RSA',
            'key_length': 2048,
            'san': ['domain3', '10.10.10.10'],
            'common': 'dev',
            'country': 'US',
            'state': 'TN',
            'city': 'Knoxville',
            'organization': 'iX',
            'organizational_unit': 'dev',
            'email': 'iamacert@ix.com',
            'digest_algorithm': 'SHA256',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'serial': 12936,
            'ca_certificate': textwrap.dedent('''
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
                    'enabled': False,
                },
                'AuthorityKeyIdentifier': {
                    'enabled': False,
                },
                'ExtendedKeyUsage': {
                    'enabled': False,
                },
                'KeyUsage': {
                    'enabled': False,
                }
            },
        }, rsa.RSAPrivateKey, 2048,
        {
            'DN': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=iamacert@ix.com/'
                  'subjectAltName=DNS:domain3, IP Address:10.10.10.10',
            'chain': False,
            'city': 'Knoxville',
            'common': 'dev',
            'country': 'US',
            'digest_algorithm': 'SHA256',
            'email': 'iamacert@ix.com',
            'extensions': {
                'SubjectAltName': 'DNS:domain3, IP Address:10.10.10.10',
            },
            'fingerprint': '5C:BF:5A:CF:76:12:48:1B:85:A0:AE:2C:5D:E0:51:85:B3:C2:40:79',
            'from': 'Mon Jan 24 11:28:07 2022',
            'issuer_dn': '/CN=dev/C=US/ST=TN/L=Knoxville/O=iX/OU=dev/emailAddress=dev@ix.com',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'organization': 'iX',
            'organizational_unit': 'dev',
            'san': ['DNS:domain3', 'IP Address:10.10.10.10'],
            'serial': 12936,
            'state': 'TN',
            'subject_name_hash': 3214950212,
            'until': 'Sat Feb 25 11:28:07 2023'
        }
    )
])
def test__generating_cert(generate_params, key_type, key_size, cert_info):
    ca_str, key = generate_certificate(generate_params)
    cert_details = load_certificate(ca_str, True)
    key_obj = load_private_key(key)
    assert isinstance(key_obj, rsa.RSAPrivateKey) is True
    assert key_obj.key_size == key_size

    # there are certain keys which are special and we should not be validating those as they would differ
    special_props = ['fingerprint', 'from', 'until', 'subject_name_hash']
    for k in cert_info:
        assert k in cert_details, cert_details

        if k in special_props:
            continue
        if k == 'extensions':
            assert 'SubjectKeyIdentifier' in cert_details[k], cert_details[k]
            cert_details[k].pop('SubjectKeyIdentifier')

        assert cert_info[k] == cert_details[k], cert_details


@pytest.mark.parametrize('data', [
    {
        'ca_certificate': textwrap.dedent('''
            -----BEGIN CERTIFICATE-----
            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
            -----END CERTIFICATE-----
        '''),
        'ca_privatekey': textwrap.dedent('''
            -----BEGIN PRIVATE KEY-----
            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
            +/ITTvwhewd07bFIPLU7UqXVIfSZNg==
            -----END PRIVATE KEY-----
        '''),
        'csr': textwrap.dedent('''
            -----BEGIN CERTIFICATE REQUEST-----
            MIIDMDCCAhgCAQAwgYExDjAMBgNVBAMMBU15Q1NSMQswCQYDVQQGEwJVUzETMBEG
            A1UECAwKQ2FsaWZvcm5pYTEUMBIGA1UEBwwLTG9zIEFuZ2VsZXMxFzAVBgNVBAoM
            Dk15T3JnYW5pemF0aW9uMR4wHAYJKoZIhvcNAQkBFg9hYmNAZXhhbXBsZS5jb20w
            ggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCoyhG7UTKGI3Mh/YWvIPQT
            E1h633JYCbEN7k/uJoCR0EwUtIZm4RT9MM1mT+uuGiFvgAvpYLtKkPDJ7/3nNvkS
            VQRFeJnNHW+pj0XzcuoCgrU6lMLid+TfSQS3yDOuFYosozBzOFW63uGNjAPU4zbf
            3hEKfeFPoJsy5q9LPoGctO/ooo1aDCwHSSPL17d8ip4Zn6VjaIXiN1nDcFIImu5U
            FJY7yGaOVItJCtrLXb489WCDNK6c39GIEFYlJCuXZY9z/SDy1qESEXlOlWBymdCv
            JuUJKHqxSIGKj0DHbbDWPLx9PbiGGuboVFuJifoqAVQpmCzFnKJdhlyNSv6sRz+J
            AgMBAAGgaTBnBgkqhkiG9w0BCQ4xWjBYMBYGA1UdEQQPMA2CC2V4YW1wbGUuY29t
            MAwGA1UdEwEB/wQCMAAwIAYDVR0lAQH/BBYwFAYIKwYBBQUHAwEGCCsGAQUFBwMC
            MA4GA1UdDwEB/wQEAwIDqDANBgkqhkiG9w0BAQsFAAOCAQEAKDO0G6K+xQGmno1x
            hoZAayj91r6PZhact54vXij9dFxUh5Z4V2AVIHlIEdfXEj494ZKIWSW46/qgkGc7
            fDUYstUjNTmLE9OzMIwXEkLlQG1RQ1sweMlvrapQ4hdxz7vO9lJ0imYrJLS5Xi1Q
            a814O4H22tvt6KeBp7I9hj2OSmTbdaNh0rNLL9eTq5PclIAshw+fw9OWqPznIj90
            55I3x14uk4TMs8gXG7IJQPtfzGLRwVWl7jhEPnTp5yEyuUHZUOGZrLHXcZk5v9Jj
            kdhmk7kTAAXsO378HZn2DZx1FlLvJjNheOtiSAV2tQpKIKCGHzDHARD7AjVXrD+1
            L4JCDA==
            -----END CERTIFICATE REQUEST-----
        '''),
        'csr_privatekey': textwrap.dedent('''
            -----BEGIN PRIVATE KEY-----
            MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCoyhG7UTKGI3Mh
            /YWvIPQTE1h633JYCbEN7k/uJoCR0EwUtIZm4RT9MM1mT+uuGiFvgAvpYLtKkPDJ
            7/3nNvkSVQRFeJnNHW+pj0XzcuoCgrU6lMLid+TfSQS3yDOuFYosozBzOFW63uGN
            jAPU4zbf3hEKfeFPoJsy5q9LPoGctO/ooo1aDCwHSSPL17d8ip4Zn6VjaIXiN1nD
            cFIImu5UFJY7yGaOVItJCtrLXb489WCDNK6c39GIEFYlJCuXZY9z/SDy1qESEXlO
            lWBymdCvJuUJKHqxSIGKj0DHbbDWPLx9PbiGGuboVFuJifoqAVQpmCzFnKJdhlyN
            Sv6sRz+JAgMBAAECggEARsp9NllfPdgXXR2l2GYTR/7YoKwfmmHyMrwNJP5b9Qvu
            JM70AakMMwapVuxVFe+ar1d+Z3KtCqCQhLlVfYhWXURv5q0moFrkrrJK7ch38fad
            CMVEmVQclzNaObRLTIt3KLKGywRJHHeHFOUw5DQpmynZbtON0GY1QVt0ELRWCwE/
            qDc9G1RVqkwn94AIdI+RScSOT1F6Ebsh0ma9PzcZEyNnvI6RaJXPF/QJOVHJPd50
            F5lSXRHwiTMFJTa7ihkl87jAYYLrjnOVPSsghSO55Fav+NqR1bO5v4A5iZr3aGGN
            3EZXmKcATqwLAai4m4LqpBwWbl4dTiLU8LfeF/CLowKBgQDUOtR6RpVLUteNeZGA
            BJt77G988qmhOhCbvzeU1h8dpN/DaReqxTlKSgh7XgdfaL9Hoi9A8WsoTAu6rAlo
            F2admQU/9OG/x2DEXXP4gyfqj64qA8i6dUjrK1lWE6O/SE79LdtH8zadoVCL6Z78
            ybQrc1jZMvR/7Zja1i7WYb9STwKBgQDLmbKfyBSC9PrP7yrnnyA0NZTINUoLhoXB
            TcyLpiDRZ20WqgFlFB8Pv2ji+E+lOF0tfCewZgPOciYDIJawXKrbGnBh+9qAzHrB
            cXNjREawGTK3g5Z2V4Y8SIz8N92pFOEe0ZLc2F25Ciy+MAfg1REK5gwwfR0lJlpr
            gtMq/6ESpwKBgQCCRJYVc+vBr1jV4w/3V1yk5UzNkhmi+AQnxWh1eDTjOkeLJ5+6
            V5LB0c2BBAdcfewjKR7+KvGOa5crftvLQ8nd5IY/aq2CzPvNrFs56C+BH65U5bu5
            D7Kxfws39ZgmGlk5uIMHl/cnLFRHfR/0pE5t+UBJGajQOWQAt0VKm/cWqwKBgQCj
            BkKc5hxmb7qU3LDCHgwvQegMF39ekyxuh9kMyMzmX6Zdy2qqgN4OQfm+I43Cgcs6
            LHurJ0RM/eGqB2IhfVHhdt4d1wgysYhpdGosRfND9ilCAD9uKs71XjJlkmYOiQVp
            I+4wn58MFzWUY+krAfBPhbyk5sl7gaZNB8gGWgGjaQKBgQCmq5QGa+WWxI7Oxq3b
            eVHijSzg+C4HVXU4L8lrvLOvze7mzjL2nw1hRsW7tq/csWD2K/ySU3ABslxDudBW
            wn+FoP5qs4E5F4bR+vt+y+3qd9WfVju5+yMVgtV6QduREyR8BbU77P67BrGP6fE+
            ojKM5TWJfQdZ2fyIKpBYunYk+A==
            -----END PRIVATE KEY-----
        '''),
        'serial': 554702452401875914103556532740307722432552646627,
        'digest_algorithm': 'SHA256',
        'cert_extensions': {
            'BasicConstraints': {
                'ca': False,
                'enabled': False,
                'path_length': None,
                'extension_critical': False
            },
            'AuthorityKeyIdentifier': {
                'authority_cert_issuer': False,
                'enabled': False,
                'extension_critical': False
            },
            'ExtendedKeyUsage': {
                'usages': [],
                'enabled': False,
                'extension_critical': False
            },
            'KeyUsage': {
                'enabled': False,
                'digital_signature': False,
                'content_commitment': False,
                'key_encipherment': False,
                'data_encipherment': False,
                'key_agreement': False,
                'key_cert_sign': False,
                'crl_sign': False,
                'encipher_only': False,
                'decipher_only': False,
                'extension_critical': False
            }
        }
    }
], ids=['Test ca_sign_csr']
)
def test_ca_sign_csr(data):
    cert = sign_csr_with_ca(data)
    cert_data = x509.load_pem_x509_certificate(cert.encode('utf-8'), default_backend())
    cert_issuer = cert_data.issuer
    ca_pem_data = data['ca_certificate'].encode('utf-8')
    ca_data = x509.load_pem_x509_certificate(ca_pem_data, default_backend())
    ca_subject = ca_data.subject
    assert cert is not None
    assert cert_issuer == ca_subject
