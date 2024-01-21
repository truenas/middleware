import errno
import contextlib
import pytest

from middlewared.client.client import ClientException, ValidationErrors
from middlewared.service_exception import ValidationErrors as ValidationErrorsServiceException
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.crypto import (
    certificate_signing_request, get_cert_params, root_certificate_authority,
)
from middlewared.test.integration.utils import call


TEST_CERTIFICATE_AUTHORITY = 'test_ca_crt'
TEST_CERTIFICATE = 'test_crt'
TEST_CSR_SIGNING = 'test_sign_csr'


@contextlib.contextmanager
def create_certificate_authority(client, name):
    ca = client.call('certificateauthority.create', {
        **get_cert_params(),
        'name': name,
        'create_type': 'CA_CREATE_INTERNAL',
    })

    try:
        yield ca
    finally:
        client.call('certificateauthority.delete', ca['id'])


@contextlib.contextmanager
def create_signing_csr(client, root_ca_id, csr_id):
    cert = client.call('certificateauthority.ca_sign_csr', {
        'ca_id': root_ca_id,
        'csr_cert_id': csr_id,
        'name': TEST_CSR_SIGNING,
    })
    try:
        yield cert
    finally:
        call('certificate.delete', cert['id'], job=True)


def common_checks(method, role, valid_role, valid_role_exception=True, method_args=None, method_kwargs=None):
    method_args = method_args or []
    method_kwargs = method_kwargs or {}
    with unprivileged_user_client(roles=[role]) as client:
        if valid_role:
            if valid_role_exception:
                with pytest.raises((ValidationErrors, ValidationErrorsServiceException)):
                    client.call(method, *method_args, **method_kwargs)
            else:
                assert client.call(method, *method_args, **method_kwargs) is not None
        else:
            with pytest.raises(ClientException) as ve:
                client.call(method, *method_args, **method_kwargs)
            assert ve.value.errno == errno.EACCES
            assert ve.value.error == 'Not authorized'


@pytest.mark.parametrize('method, role, valid_role', (
    ('certificate.profiles', 'CERTIFICATE_READ', True),
    ('certificateauthority.profiles', 'CERTIFICATEAUTHORITY_READ', True),
    ('certificate.profiles', 'CERTIFICATEAUTHORITY_READ', False),
    ('certificateauthority.profiles', 'CERTIFICATE_READ', False),
))
def test_profiles_read_roles(method, role, valid_role):
    common_checks(method, role, valid_role, valid_role_exception=False)


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATEAUTHORITY_WRITE', True),
    ('CERTIFICATEAUTHORITY_READ', False),
))
def test_certificate_authority_create_role(role, valid_role):
    common_checks('certificateauthority.create', role, valid_role, method_args=[{}])


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_WRITE', True),
    ('CERTIFICATE_READ', False),
))
def test_certificate_create_role(role, valid_role):
    common_checks('certificate.create', role, valid_role, method_args=[{}], method_kwargs={'job': True})


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATEAUTHORITY_WRITE', True),
    ('CERTIFICATEAUTHORITY_READ', False),
))
def test_signing_csr_role(role, valid_role):
    with root_certificate_authority(TEST_CERTIFICATE_AUTHORITY) as root_ca:
        with certificate_signing_request(TEST_CERTIFICATE) as csr:
            with unprivileged_user_client(roles=[role]) as c:
                if valid_role:
                    with create_signing_csr(c, root_ca['id'], csr['id']) as crt:
                        assert crt is not None
                else:
                    with pytest.raises(ClientException) as ve:
                        with create_signing_csr(c, root_ca['id'], csr['id']):
                            pass
                    assert ve.value.errno == errno.EACCES
                    assert ve.value.error == 'Not authorized'
