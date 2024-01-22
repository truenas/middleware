import errno
import pytest

from middlewared.client.client import ClientException, ValidationErrors
from middlewared.service_exception import ValidationErrors as ValidationErrorsServiceException
from middlewared.test.integration.assets.account import unprivileged_user_client


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
    ('certificateauthority.profiles', 'CERTIFICATE_AUTHORITY_READ', True),
    ('certificate.profiles', 'CERTIFICATE_AUTHORITY_READ', False),
    ('certificateauthority.profiles', 'CERTIFICATE_READ', False),
))
def test_profiles_read_roles(method, role, valid_role):
    common_checks(method, role, valid_role, valid_role_exception=False)


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_AUTHORITY_WRITE', True),
    ('CERTIFICATE_AUTHORITY_READ', False),
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
    ('CERTIFICATE_AUTHORITY_WRITE', True),
    ('CERTIFICATE_AUTHORITY_READ', False),
))
def test_signing_csr_role(role, valid_role):
    common_checks('certificateauthority.ca_sign_csr', role, valid_role, method_args=[{
        'ca_id': 1,
        'csr_cert_id': 1,
        'name': 'test_csr_signing_role',
    }])
