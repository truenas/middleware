import pytest

from middlewared.test.integration.assets.crypto import (
    certificate_signing_request, get_cert_params, intermediate_certificate_authority, root_certificate_authority
)
from middlewared.test.integration.utils import call

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


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
