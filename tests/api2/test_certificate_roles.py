import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_WRITE', True),
    ('CERTIFICATE_READ', False),
))
def test_certificate_create_role(unprivileged_user_fixture, role, valid_role):
    common_checks(
        unprivileged_user_fixture, 'certificate.create', role, valid_role, method_args=[], method_kwargs={'job': True}
    )


# For update/delete the role check happens before argument validation, so a bogus
# ID is fine: with a valid role the call still raises (e.g. instance-not-found),
# but NOT with EACCES; with an invalid role it raises EACCES, which is what
# common_checks asserts.
_BOGUS_ID = 999999


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_WRITE', True),
    ('CERTIFICATE_READ', False),
))
def test_certificate_update_role(unprivileged_user_fixture, role, valid_role):
    common_checks(
        unprivileged_user_fixture, 'certificate.update', role, valid_role,
        method_args=[_BOGUS_ID, {}], method_kwargs={'job': True},
    )


@pytest.mark.parametrize('role, valid_role', (
    ('CERTIFICATE_WRITE', True),
    ('CERTIFICATE_READ', False),
))
def test_certificate_delete_role(unprivileged_user_fixture, role, valid_role):
    common_checks(
        unprivileged_user_fixture, 'certificate.delete', role, valid_role,
        method_args=[_BOGUS_ID], method_kwargs={'job': True},
    )
