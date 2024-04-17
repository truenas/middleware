import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('method, role, valid_role', (
    ('certificate.profiles', 'CERTIFICATE_READ', True),
    ('certificateauthority.profiles', 'CERTIFICATE_AUTHORITY_READ', True),
    ('certificate.profiles', 'CERTIFICATE_AUTHORITY_READ', False),
    ('certificateauthority.profiles', 'CERTIFICATE_READ', False),
))
def test_profiles_read_roles(unprivileged_user_fixture, method, role, valid_role):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=False)


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_AUTHORITY_WRITE', True),
    ('CERTIFICATE_AUTHORITY_READ', False),
))
def test_certificate_authority_create_role(unprivileged_user_fixture, role, valid_role):
    common_checks(unprivileged_user_fixture, 'certificateauthority.create', role, valid_role, method_args=[{}])


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_WRITE', True),
    ('CERTIFICATE_READ', False),
))
def test_certificate_create_role(unprivileged_user_fixture, role, valid_role):
    common_checks(unprivileged_user_fixture, 'certificate.create', role, valid_role, method_args=[], method_kwargs={'job': True})


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_AUTHORITY_WRITE', True),
    ('CERTIFICATE_AUTHORITY_READ', False),
))
def test_signing_csr_role(unprivileged_user_fixture, role, valid_role):
    common_checks(unprivileged_user_fixture, 'certificateauthority.ca_sign_csr', role, valid_role, method_args=[{
        'ca_id': 1,
        'csr_cert_id': 1,
        'name': 'test_csr_signing_role',
    }])
