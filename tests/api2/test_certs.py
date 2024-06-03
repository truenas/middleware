import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.crypto import (
    certificate_signing_request, get_cert_params, intermediate_certificate_authority, root_certificate_authority
)
from middlewared.test.integration.utils import call

import sys
import textwrap
import os
apifolder = os.getcwd()
sys.path.append(apifolder)


# We would like to test the following cases
# Creating root CA
# Creating intermediate CA
# Importing CA
# Creating certificate from root/intermediate CAs
# Create CSR
# Signing CSR

def test_creating_root_ca():
    root_ca = call('certificateauthority.create', {
        **get_cert_params(),
        'name': 'test_root_ca',
        'create_type': 'CA_CREATE_INTERNAL',
    })
    try:
        assert root_ca['CA_type_internal'] is True, root_ca
    finally:
        call('certificateauthority.delete', root_ca['id'])


def test_root_ca_issuer_reported_correctly():
    with root_certificate_authority('root_ca_test') as root_ca:
        assert root_ca['issuer'] == 'self-signed', root_ca


def test_creating_intermediate_ca():
    with root_certificate_authority('root_ca_test') as root_ca:
        intermediate_ca = call('certificateauthority.create', {
            **get_cert_params(),
            'signedby': root_ca['id'],
            'name': 'test_intermediate_ca',
            'create_type': 'CA_CREATE_INTERMEDIATE',
        })
        try:
            assert intermediate_ca['CA_type_intermediate'] is True, intermediate_ca
        finally:
            call('certificateauthority.delete', intermediate_ca['id'])


def test_ca_intermediate_issuer_reported_correctly():
    with root_certificate_authority('root_ca_test') as root_ca:
        intermediate_ca = call('certificateauthority.create', {
            **get_cert_params(),
            'signedby': root_ca['id'],
            'name': 'test_intermediate_ca',
            'create_type': 'CA_CREATE_INTERMEDIATE',
        })
        root_ca = call('certificateauthority.get_instance', root_ca['id'])
        try:
            assert intermediate_ca['issuer'] == root_ca, intermediate_ca
        finally:
            call('certificateauthority.delete', intermediate_ca['id'])


def test_cert_chain_of_intermediate_ca_reported_correctly():
    with root_certificate_authority('root_ca_test') as root_ca:
        intermediate_ca = call('certificateauthority.create', {
            **get_cert_params(),
            'signedby': root_ca['id'],
            'name': 'test_intermediate_ca',
            'create_type': 'CA_CREATE_INTERMEDIATE',
        })
        try:
            assert intermediate_ca['chain_list'] == [
                intermediate_ca['certificate'], root_ca['certificate']
            ], intermediate_ca
        finally:
            call('certificateauthority.delete', intermediate_ca['id'])


def test_importing_ca():
    with root_certificate_authority('root_ca_test') as root_ca:
        imported_ca = call('certificateauthority.create', {
            'certificate': root_ca['certificate'],
            'privatekey': root_ca['privatekey'],
            'name': 'test_imported_ca',
            'create_type': 'CA_CREATE_IMPORTED',
        })
        try:
            assert imported_ca['CA_type_existing'] is True, imported_ca
        finally:
            call('certificateauthority.delete', imported_ca['id'])


def test_ca_imported_issuer_reported_correctly():
    with root_certificate_authority('root_ca_test') as root_ca:
        imported_ca = call('certificateauthority.create', {
            'certificate': root_ca['certificate'],
            'privatekey': root_ca['privatekey'],
            'name': 'test_imported_ca',
            'create_type': 'CA_CREATE_IMPORTED',
        })
        try:
            assert imported_ca['issuer'] == 'external', imported_ca
        finally:
            call('certificateauthority.delete', imported_ca['id'])


def test_ca_imported_add_to_trusted_store_reported_correctly():
    with root_certificate_authority('root_ca_test') as root_ca:
        imported_ca = call('certificateauthority.create', {
            'certificate': root_ca['certificate'],
            'privatekey': root_ca['privatekey'],
            'name': 'test_tinkerbell',
            'add_to_trusted_store': True,
            'create_type': 'CA_CREATE_IMPORTED',
        })
        try:
            assert imported_ca['add_to_trusted_store'] is True, imported_ca
        finally:
            call('certificateauthority.delete', imported_ca['id'])


def test_creating_cert_from_root_ca():
    with root_certificate_authority('root_ca_test') as root_ca:
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': root_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        try:
            assert cert['cert_type_internal'] is True, cert
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_cert_chain_of_root_ca_reported_correctly():
    with root_certificate_authority('root_ca_test') as root_ca:
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': root_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        try:
            assert cert['chain_list'] == [cert['certificate'], root_ca['certificate']], cert
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_creating_cert_from_intermediate_ca():
    with intermediate_certificate_authority('root_ca', 'intermediate_ca') as (root_ca, intermediate_ca):
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': intermediate_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        try:
            assert cert['cert_type_internal'] is True, cert
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_cert_chain_reported_correctly():
    with intermediate_certificate_authority('root_ca', 'intermediate_ca') as (root_ca, intermediate_ca):
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': intermediate_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        try:
            assert cert['chain_list'] == [
                cert['certificate'], intermediate_ca['certificate'], root_ca['certificate']
            ], cert
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_cert_issuer_reported_correctly():
    with intermediate_certificate_authority('root_ca', 'intermediate_ca') as (root_ca, intermediate_ca):
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': intermediate_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        intermediate_ca = call('certificateauthority.get_instance', intermediate_ca['id'])
        try:
            assert cert['issuer'] == intermediate_ca, cert
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_creating_csr():
    with certificate_signing_request('csr_test') as csr:
        assert csr['cert_type_CSR'] is True, csr


def test_issuer_of_csr():
    with certificate_signing_request('csr_test') as csr:
        assert csr['issuer'] == 'external - signature pending', csr


def test_signing_csr():
    with root_certificate_authority('root_ca') as root_ca:
        with certificate_signing_request('csr_test') as csr:
            cert = call('certificateauthority.ca_sign_csr', {
                'ca_id': root_ca['id'],
                'csr_cert_id': csr['id'],
                'name': 'signed_cert',
            })
            root_ca = call('certificateauthority.get_instance', root_ca['id'])
            try:
                assert isinstance(cert['signedby'], dict), cert
                assert cert['signedby']['id'] == root_ca['id'], cert
                assert cert['chain_list'] == [cert['certificate'], root_ca['certificate']]
                assert cert['issuer'] == root_ca, cert
            finally:
                call('certificate.delete', cert['id'], job=True)


def test_revoking_cert():
    with intermediate_certificate_authority('root_ca', 'intermediate_ca') as (root_ca, intermediate_ca):
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': intermediate_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        try:
            assert cert['can_be_revoked'] is True, cert
            cert = call('certificate.update', cert['id'], {'revoked': True}, job=True)
            assert cert['revoked'] is True, cert

            root_ca = call('certificateauthority.get_instance', root_ca['id'])
            intermediate_ca = call('certificateauthority.get_instance', intermediate_ca['id'])

            assert len(root_ca['revoked_certs']) == 1, root_ca
            assert len(intermediate_ca['revoked_certs']) == 1, intermediate_ca

            assert root_ca['revoked_certs'][0]['certificate'] == cert['certificate'], root_ca
            assert intermediate_ca['revoked_certs'][0]['certificate'] == cert['certificate'], intermediate_ca
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_revoking_ca():
    with intermediate_certificate_authority('root_ca', 'intermediate_ca') as (root_ca, intermediate_ca):
        cert = call('certificate.create', {
            'name': 'cert_test',
            'signedby': intermediate_ca['id'],
            'create_type': 'CERTIFICATE_CREATE_INTERNAL',
            **get_cert_params(),
        }, job=True)
        try:
            assert intermediate_ca['can_be_revoked'] is True, intermediate_ca
            intermediate_ca = call('certificateauthority.update', intermediate_ca['id'], {'revoked': True})
            assert intermediate_ca['revoked'] is True, intermediate_ca

            cert = call('certificate.get_instance', cert['id'])
            assert cert['revoked'] is True, cert

            root_ca = call('certificateauthority.get_instance', root_ca['id'])
            assert len(root_ca['revoked_certs']) == 2, root_ca
            assert len(intermediate_ca['revoked_certs']) == 2, intermediate_ca

            check_set = {intermediate_ca['certificate'], cert['certificate']}
            assert set(c['certificate'] for c in intermediate_ca['revoked_certs']) == check_set, intermediate_ca
            assert set(c['certificate'] for c in root_ca['revoked_certs']) == check_set, root_ca
        finally:
            call('certificate.delete', cert['id'], job=True)


def test_created_certs_exist_on_filesystem():
    with intermediate_certificate_authority('root_ca', 'intermediate_ca') as (root_ca, intermediate_ca):
        with certificate_signing_request('csr_test') as csr:
            cert = call('certificate.create', {
                'name': 'cert_test',
                'signedby': intermediate_ca['id'],
                'create_type': 'CERTIFICATE_CREATE_INTERNAL',
                **get_cert_params(),
            }, job=True)
            try:
                assert get_cert_current_files() == get_cert_expected_files()
            finally:
                call('certificate.delete', cert['id'], job=True)


def test_deleted_certs_dont_exist_on_filesystem():
    with intermediate_certificate_authority('root_ca2', 'intermediate_ca2') as (root_ca2, intermediate_ca2):
        # no-op
        pass
    with certificate_signing_request('csr_test2') as csr2:
        pass
    assert get_cert_current_files() == get_cert_expected_files()


def get_cert_expected_files():
    certs = call('certificate.query')
    cas = call('certificateauthority.query')
    expected_files = {'/etc/certificates/CA'}
    for cert in certs + cas:
        if cert['chain_list']:
            expected_files.add(cert['certificate_path'])
        if cert['privatekey']:
            expected_files.add(cert['privatekey_path'])
        if cert['cert_type_CSR']:
            expected_files.add(cert['csr_path'])
        if any(cert[k] for k in ('CA_type_existing', 'CA_type_internal', 'CA_type_intermediate')):
            expected_files.add(cert['crl_path'])
    return expected_files


def get_cert_current_files():
    return {
        f['path']
        for p in ('/etc/certificates', '/etc/certificates/CA') for f in call('filesystem.listdir', p)
    }


@pytest.mark.parametrize('life_time,should_work', [
    (300, True),
    (9999999, False),
])
def test_certificate_lifetime_validation(life_time, should_work):
    cert_params = get_cert_params()
    cert_params['lifetime'] = life_time
    with root_certificate_authority('root-ca') as root_ca:
        if should_work:
            cert = None
            try:
                cert = call(
                    'certificate.create', {
                        'name': 'test-cert',
                        'create_type': 'CERTIFICATE_CREATE_INTERNAL',
                        'signedby': root_ca['id'],
                        **cert_params,
                    }, job=True
                )
                assert cert['parsed'] is True, cert
            finally:
                if cert:
                    call('certificate.delete', cert['id'], job=True)
        else:
            with pytest.raises(ValidationErrors):
                call(
                    'certificate.create', {
                        'name': 'test-cert',
                        'signedby': root_ca['id'],
                        'create_type': 'CERTIFICATE_CREATE_INTERNAL',
                        **cert_params,
                    }, job=True
                )


@pytest.mark.parametrize('certificate,private_key,should_work', [
    (
        textwrap.dedent('''\
            -----BEGIN CERTIFICATE-----
            MIIEDTCCAvWgAwIBAgIEAKWUWTANBgkqhkiG9w0BAQsFADBVMQswCQYDVQQGEwJV
            UzEMMAoGA1UECAwDdXNhMRMwEQYDVQQHDApjYWxpZm9ybmlhMQswCQYDVQQKDAJs
            bTEWMBQGCSqGSIb3DQEJARYHYUBiLmNvbTAeFw0yMzA0MDYxNjQyMTJaFw0yNDA1
            MDcxNjQyMTJaME4xCzAJBgNVBAYTAlVTMQwwCgYDVQQIDAN1c2ExDDAKBgNVBAcM
            A3VzYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYy5jb20wggEiMA0G
            CSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCtvPEA2x3/jp0riSdgb7TqB9uAobzt
            tYbW9E0+WLqf3sLJJ4F4Iq0AI1YYMtOOwcjmvC52eSaqxoGcY4G2J+RgQNR8b8lk
            m38vRYQA2SkDCtEQFkLiCrkr5g20xh89gCLEr9c5x45p8Pl7q2LmE6wVIVjWqTSi
            Yo4TMD8Nb5LN3vPeM7+fwV7FZDH7PJ4AT1/kTJjhkK0wiOGeTLEW5wiSYO8QMD0r
            JHfzAp8UPFsVK8InZTjLS4VJgI0OlG2Von7Nv7Wtxsg5hi7dkLu2tawHE8DD97O5
            zhVTZHzBiDF1mrjR3+6RWgn8iF6353UV9hbyPYz51UiCEYHBwFtqQaBlAgMBAAGj
            geswgegwDgYDVR0RBAcwBYIDYWJjMB0GA1UdDgQWBBSRzlS66ts6rhuCN+4VK2x7
            8E+n1zAMBgNVHRMBAf8EAjAAMIGABgNVHSMEeTB3gBR1fZ31S5XHrijsT/C9fzbB
            aqrg5qFZpFcwVTELMAkGA1UEBhMCVVMxDDAKBgNVBAgMA3VzYTETMBEGA1UEBwwK
            Y2FsaWZvcm5pYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYi5jb22C
            BACllFgwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwIwDgYDVR0PAQH/BAQDAgOIMA0G
            CSqGSIb3DQEBCwUAA4IBAQA7UwYNr6gspgRcCGwzl5RUAL/N3NXv3rcgTPF405s5
            OXKDPAxWSulzt/jqAesYvI27koOsGj0sDsSRLRdmj4HG91Xantnv5rxGqdYHEDPo
            j8oo1HQv8vqhDcKUJOKH5j5cWO+W75CpAHuMfgxKJ9WdxPSNpKZoOKIMd2hwd4ng
            2+ulgfvVKcE4PM4YSrtW4qoAoz/+gyfwSoIAQJ0VOuEwL+QFJ8Ud1aJaJRkLD39P
            uLEje++rBbfIX9VPCRS/c3gYAOHu66LYI3toTomY8U3YYiQk8bC3Rp9uAjmgI3br
            4DHLwRTEUbOL8CdNcGb1qvO8xBSRzjMIZM8QJHSyYNcM
            -----END CERTIFICATE-----
        '''),
        textwrap.dedent('''\
            -----BEGIN PRIVATE KEY-----
            MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCtvPEA2x3/jp0r
            iSdgb7TqB9uAobzttYbW9E0+WLqf3sLJJ4F4Iq0AI1YYMtOOwcjmvC52eSaqxoGc
            Y4G2J+RgQNR8b8lkm38vRYQA2SkDCtEQFkLiCrkr5g20xh89gCLEr9c5x45p8Pl7
            q2LmE6wVIVjWqTSiYo4TMD8Nb5LN3vPeM7+fwV7FZDH7PJ4AT1/kTJjhkK0wiOGe
            TLEW5wiSYO8QMD0rJHfzAp8UPFsVK8InZTjLS4VJgI0OlG2Von7Nv7Wtxsg5hi7d
            kLu2tawHE8DD97O5zhVTZHzBiDF1mrjR3+6RWgn8iF6353UV9hbyPYz51UiCEYHB
            wFtqQaBlAgMBAAECggEAFNc827rtIspDPUUzFYTg4U/2+zurk6I6Xg+pMmjnXiUV
            HZchFz2lngYfHkD+krnZNSBuvGR1CHhOdOmU1jp70TYFpzWrpWdnvs5qcsWZ/1Tt
            Vi4tcLsTkloC2+QGPFTiFtD3EuXGxhuTecvJzcqfUluRMhLTDwWegFvBvIVdSVeZ
            9XFDZF9O748tdt2PhYcL2L/xDz4sIz89ek4P1v4raB52rcleIduqMat29crVR3ex
            VsZK3PLW6HCquUQvdvjLblfzjDS1pqcpIiSsYCrP0eEEKrrg44V8VjcPxXIg4GAE
            ioDOpi9vO/3xyxYxXBtlD2o6c9kZUrp+xxx9jztdIQKBgQDo8witC33Z7Rd6dLm9
            zgN/wZ2lWqE927fXZBExKjCXZ+A3N58One0TR2qI9S+BRVc2KOCWFGUjnHbx1PfE
            xU1UNDY+ir9Lqk+rzhyEk4vst/IwhyovmAhL5fONqlfxB+l29cUh6JIYMtqaWYvj
            AbmS5YhZRMa3kI/BtCTRJtPecQKBgQC+7f57XWt7HNe7FvrDTz5M8AmQ7y487NxZ
            OcZ1+YKJ57PVY7G7Ye3xqRTd05L6h1P1eCO0gLDiSy5VOz47uFdNcD/9Ia+Ng2oq
            P8TC36b86dz3ZDhBm4AB3shaD/JBjUQ0NwLosmrMaDF+lVu8NPA60eeQ70/RgbSA
            KNrOUH1DNQKBgQDicOzsGZGat6fs925enNY16CWwSOsYUG7ix3kWy6Y0Z1tDEaRh
            9w4vgWqD+6LUDG18TjwSZ3zxIvVUmurGsew7gA2Cuii+Cq4rmc2K6kpIL38TwTA2
            15io/rzD5uRZfpFpe/rGvWbWcwigpY8fedvEea8S55IrejDj4JMxZIbrYQKBgQCG
            Ke68+XRhWm8thIRJYhHBNptCQRAYt8hO2o5esCnOhgaUWC24IqR1P/7tsZKCgT26
            K+XLHPMu0O2J7stYY7zVKZ+NXHJj2ohrj8vPtCE/b4ZaQQ5W69ITfl0DDFmLPp1C
            o7Vjlpv9bun4rTN9GSYF7yHtcnyAF8iilhLLDzw2UQKBgQC4FzI6/P2HcUNzf+/m
            AThk8+4V35gOSxn3uk48CXNStcCoLMEeXM69SGYq8GaGU/piaog9D8RvF4yMAnnL
            wNpy8J/4ldluyidX61N0dMS+NL4l4TPjTvOY22KzjwfnBoqzg+93Mt//M4HfR/ka
            3EWl5VmzbuEeytrcH3uHAUpkKg==
            -----END PRIVATE KEY-----
        '''),
        True,
    ),
    (
        textwrap.dedent('''\
           -----BEGIN CERTIFICATE-----
           MIIEDTCCAvWgAwIBAgIEAKWUWTANBgkqhkiG9w0BAQsFADBVMQswCQYDVQQGEwJV
           UzEMMAoGA1UECAwDdXNhMRMwEQYDVQQHDApjYWxpZm9ybmlhMQswCQYDVQQKDAJs
           bTEWMBQGCSqGSIb3DQEJARYHYUBiLmNvbTAeFw0yMzA0MDYxNjQyMTJaFw0yNDA1
           MDcxNjQyMTJaME4xCzAJBgNVBAYTAlVTMQwwCgYDVQQIDAN1c2ExDDAKBgNVBAcM
           A3VzYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYy5jb20wggEiMA0G
           CSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCtvPEA2x3/jp0riSdgb7TqB9uAobzt
           tYbW9E0+WLqf3sLJJ4F4Iq0AI1YYMtOOwcjmvC52eSaqxoGcY4G2J+RgQNR8b8lk
           m38vRYQA2SkDCtEQFkLiCrkr5g20xh89gCLEr9c5x45p8Pl7q2LmE6wVIVjWqTSi
           Yo4TMD8Nb5LN3vPeM7+fwV7FZDH7PJ4AT1/kTJjhkK0wiOGeTLEW5wiSYO8QMD0r
           JHfzAp8UPFsVK8InZTjLS4VJgI0OlG2Von7Nv7Wtxsg5hi7dkLu2tawHE8DD97O5
           zhVTZHzBiDF1mrjR3+6RWgn8iF6353UV9hbyPYz51UiCEYHBwFtqQaBlAgMBAAGj
           geswgegwDgYDVR0RBAcwBYIDYWJjMB0GA1UdDgQWBBSRzlS66ts6rhuCN+4VK2x7
           8E+n1zAMBgNVHRMBAf8EAjAAMIGABgNVHSMEeTB3gBR1fZ31S5XHrijsT/C9fzbB
           aqrg5qFZpFcwVTELMAkGA1UEBhMCVVMxDDAKBgNVBAgMA3VzYTETMBEGA1UEBwwK
           Y2FsaWZvcm5pYTELMAkGA1UECgwCbG0xFjAUBgkqhkiG9w0BCQEWB2FAYi5jb22C
           BACllFgwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwIwDgYDVR0PAQH/BAQDAgOIMA0G
           CSqGSIb3DQEBCwUAA4IBAQA7UwYNr6gspgRcCGwzl5RUAL/N3NXv3rcgTPF405s5
           OXKDPAxWSulzt/jqAesYvI27koOsGj0sDsSRLRdmj4HG91Xantnv5rxGqdYHEDPo
           j8oo1HQv8vqhDcKUJOKH5j5cWO+W75CpAHuMfgxKJ9WdxPSNpKZoOKIMd2hwd4ng
           2+ulgfvVKcE4PM4YSrtW4qoAoz/+gyfwSoIAQJ0VOuEwL+QFJ8Ud1aJaJRkLD39P
           uLEje++rBbfIX9VPCRS/c3gYAOHu66LYI3toTomY8U3YYiQk8bC3Rp9uAjmgI3br
           4DHLwRTEUbOL8CdNcGb1qvO8xBSRzjMIZM8QJHSyYNcM
           -----END CERTIFICATE-----
        '''),
        textwrap.dedent('''\
            -----BEGIN PRIVATE KEY-----
            MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDVMPccUqq6jd8h
            h0ybrwRkvK+pvOJze00IK7F6A8RRyCwDL2Yc0GpWR5ecY+jBiZ1n+TfKfaybdKR0
            0hhFFuU74JTsUk298hI1GVBNvwbimgraQciWjg0wDjHAN7AFZL8Jb/Tn7/DZlmn+
            TgqdPaFIeD4XnLX6zwrc4VemKYDDcdr5JyDVCt3ZtqTEbbtxQ4WvZbtCxlzlkyJu
            xwdmGyCvjkQri55+FaejvnPCUzJSOK28jShBuZCIS3lR7HCcAS4cc05TTrWSZr+i
            brLISVEz1XASc0pKz8QGMuz5Hk5uNRLl4JGmWZrSV9lqtFYP9hatpLi5mnhWpgYi
            Q0IXvNUXAgMBAAECggEAdbgf+0e6dmC4gO8Q4jZ2GpoF9ZgTAulm08gsq89ArFf3
            1ZpqrCZ5UUMe+IBCmfu/KxZ2NB3JHd3+oXMRa7UEx1dvZD7eJrBwVVmw+f0tdBrT
            O0lv1ZKCvbJYzmbxj0jeI/vqI9heCggAZyf4vHK3iCi9QJSL9/4zZVwY5eus6j4G
            RCMXW8ZqiKX3GLtCjPmZilYQHNDbsfAbqy75AsG81fgaKkYkJS29rte9R34BajZs
            OFm+y6nIe6zsf0vhn/yPVN4Yhuu/WhkvqouR2NhSF7ulXckuR/ef55GPpbRcpSOj
            VUkwJL3wsHPozvmcks/TnZbqj0u7XBGjZ2VK8sF+gQKBgQDsJGMeeaua5pOITVHk
            reHaxy4tLs1+98++L9SffBbsQcCu4OdgMBizCXuUw9bHlMx19B/B56cJst239li3
            dHfC/mF4/8em5XOx97FyC0rF02qYCPXViTrTSovSEWHuM/ChmhaRlZdp5F4EBMp7
            ELdf4OBCHGz47UCLQF75/FPtJwKBgQDnHn9HuFepY+yV1sNcPKj1GfciaseKzTk1
            Iw5VVtqyS2p8vdXNUiJmaF0245S3phRBL6PDhdfd3SwMmNYvhTYsqBc6ZRHO4b9J
            SjmHct63286NuEn0piYaa3MZ8sV/xI0a5leAdkzyqPTCcn0HlvDL0HTV34umdmfj
            kqC4jsWukQKBgC48cavl5tPNkdV+TiqYYUCU/1WZdGMH4oU6mEch5NsdhLy5DJSo
            1i04DhpyvfsWB3KQ+ibdVLdxbjg24+gHxetII42th0oGY0DVXskVrO5PFu/t0TSe
            SgZU8kuPW71oLhV2NjULNTpmnIHs7jhqbX04arCHIE8dJSYe1HneDhDBAoGBALTk
            4txgxYQYaNFykd/8voVwuETg7KOQM0mK0aor2+qXKpbOAqy8r54V63eNsxX20H2g
            6v2bIbVOai7F5Ua2bguP2PZkqwaRHKYhiVuhpf6j9UxpRMFO1h3xodpacQiq74Jx
            bWVnspxvb3tOHtw04O21j+ziFizJGlE9r7wkS0dxAoGAeq/Ecb+nJp/Ce4h5US1O
            4rruiLLYMkcFGmhSMcQ+lVbGOn4eSpqrGWn888Db2oiu7mv+u0TK9ViXwHkfp4FP
            Hnm0S8e25py1Lj+bk1tH0ku1I8qcAtihYBtSwPGj+66Qyr8KOlxZP2Scvcqu+zBc
            cyhsrrlRc3Gky9L5gtdxdeo=
            -----END PRIVATE KEY-----
        '''),
        False,
    ),
    (
        textwrap.dedent('''\
           -----BEGIN CERTIFICATE-----
           ntnv5rxGqdYHEDPo
           j8oo1HQv8vqhDcKUJOKH5j5cWO+W75CpAHuMfgxKJ9WdxPSNpKZoOKIMd2hwd4ng
           2+ulgfvVKcE4PM4YSrtW4qoAoz/+gyfwSoIAQJ0VOuEwL+QFJ8Ud1aJaJRkLD39P
           uLEje++rBbfIX9VPCRS/c3gYAOHu66LYI3toTomY8U3YYiQk8bC3Rp9uAjmgI3br
           4DHLwRTEUbOL8CdNcGb1qvO8xBSRzjMIZM8QJHSyYNcM
           -----END CERTIFICATE-----
        '''),
        textwrap.dedent('''\
            -----BEGIN PRIVATE KEY-----
            MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDVMPccUqq6jd8h
            h0ybrwRkvK+pvOJze00IK7F6A8RRyCwDL2Yc0GpWR5ecY+jBiZ1n+TfKfaybdKR0
            0hhFFuU74JTsUk298hI1GVBNvwbimgraQciWjg0wDjHAN7AFZL8Jb/Tn7/DZlmn+
            TgqdPaFIeD4XnLX6zwrc4VemKYDDcdr5JyDVCt3ZtqTEbbtxQ4WvZbtCxlzlkyJu
            xwdmGyCvjkQri55+FaejvnPCUzJSOK28jShBuZCIS3lR7HCcAS4cc05TTrWSZr+i
            brLISVEz1XASc0pKz8QGMuz5Hk5uNRLl4JGmWZrSV9lqtFYP9hatpLi5mnhWpgYi
            Q0IXvNUXAgMBAAECggEAdbgf+0e6dmC4gO8Q4jZ2GpoF9ZgTAulm08gsq89ArFf3
            1ZpqrCZ5UUMe+IBCmfu/KxZ2NB3JHd3+oXMRa7UEx1dvZD7eJrBwVVmw+f0tdBrT
            O0lv1ZKCvbJYzmbxj0jeI/vqI9heCggAZyf4vHK3iCi9QJSL9/4zZVwY5eus6j4G
            RCMXW8ZqiKX3GLtCjPmZilYQHNDbsfAbqy75AsG81fgaKkYkJS29rte9R34BajZs
            OFm+y6nIe6zsf0vhn/yPVN4Yhuu/WhkvqouR2NhSF7ulXckuR/ef55GPpbRcpSOj
            VUkwJL3wsHPozvmcks/TnZbqj0u7XBGjZ2VK8sF+gQKBgQDsJGMeeaua5pOITVHk
            reHaxy4tLs1+98++L9SffBbsQcCu4OdgMBizCXuUw9bHlMx19B/B56cJst239li3
            dHfC/mF4/8em5XOx97FyC0rF02qYCPXViTrTSovSEWHuM/ChmhaRlZdp5F4EBMp7
            ELdf4OBCHGz47UCLQF75/FPtJwKBgQDnHn9HuFepY+yV1sNcPKj1GfciaseKzTk1
            Iw5VVtqyS2p8vdXNUiJmaF0245S3phRBL6PDhdfd3SwMmNYvhTYsqBc6ZRHO4b9J
            SjmHct63286NuEn0piYaa3MZ8sV/xI0a5leAdkzyqPTCcn0HlvDL0HTV34umdmfj
            kqC4jsWukQKBgC48cavl5tPNkdV+TiqYYUCU/1WZdGMH4oU6mEch5NsdhLy5DJSo
            1i04DhpyvfsWB3KQ+ibdVLdxbjg24+gHxetII42th0oGY0DVXskVrO5PFu/t0TSe
            SgZU8kuPW71oLhV2NjULNTpmnIHs7jhqbX04arCHIE8dJSYe1HneDhDBAoGBALTk
            4txgxYQYaNFykd/8voVwuETg7KOQM0mK0aor2+qXKpbOAqy8r54V63eNsxX20H2g
            6v2bIbVOai7F5Ua2bguP2PZkqwaRHKYhiVuhpf6j9UxpRMFO1h3xodpacQiq74Jx
            bWVnspxvb3tOHtw04O21j+ziFizJGlE9r7wkS0dxAoGAeq/Ecb+nJp/Ce4h5US1O
            4rruiLLYMkcFGmhSMcQ+lVbGOn4eSpqrGWn888Db2oiu7mv+u0TK9ViXwHkfp4FP
            Hnm0S8e25py1Lj+bk1tH0ku1I8qcAtihYBtSwPGj+66Qyr8KOlxZP2Scvcqu+zBc
            cyhsrrlRc3Gky9L5gtdxdeo=
            -----END PRIVATE KEY-----
        '''),
        False,
    )
], ids=['valid_cert', 'invalid_cert', 'invalid_cert'])
def test_importing_certificate_validation(certificate, private_key, should_work):
    cert_params = {'certificate': certificate, 'privatekey': private_key}
    if should_work:
        cert = None
        if should_work:
            try:
                cert = call(
                    'certificate.create', {
                        'name': 'test-cert',
                        'create_type': 'CERTIFICATE_CREATE_IMPORTED',
                        **cert_params,
                    }, job=True
                )
                assert cert['parsed'] is True, cert
            finally:
                if cert:
                    call('certificate.delete', cert['id'], job=True)

        else:
            with pytest.raises(ValidationErrors):
                call(
                    'certificate.create', {
                        'name': 'test-cert',
                        'create_type': 'CERTIFICATE_CREATE_IMPORTED',
                        **cert_params,
                    }, job=True
                )
