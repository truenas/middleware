import pytest

from middlewared.test.integration.assets.crypto import (
    get_cert_params, intermediate_certificate_authority, root_certificate_authority
)
from middlewared.test.integration.utils import call, ssh

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
    cert_params = get_cert_params()
    cert_params.pop('lifetime')
    csr = call('certificate.create', {
        'name': 'csr_test',
        'create_type': 'CERTIFICATE_CREATE_CSR',
        **cert_params,
    }, job=True)
    try:
        assert csr['cert_type_CSR'] is True, csr
    finally:
        call('certificate.delete', csr['id'], job=True)


def test_issuer_of_csr():
    cert_params = get_cert_params()
    cert_params.pop('lifetime')
    csr = call('certificate.create', {
        'name': 'csr_test',
        'create_type': 'CERTIFICATE_CREATE_CSR',
        **cert_params,
    }, job=True)
    try:
        assert csr['issuer'] == 'external - signature pending', csr
    finally:
        call('certificate.delete', csr['id'], job=True)
