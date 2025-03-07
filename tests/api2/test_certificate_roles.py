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
