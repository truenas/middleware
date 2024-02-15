import pytest

from middlewared.test.integration.assets.roles import common_checks


def test_truecommand_readonly_role():
    common_checks(
        'truecommand.connected', 'READONLY_ADMIN', True, valid_role_exception=False
    )


@pytest.mark.parametrize('endpoint,role,should_work,valid_role_exception', [
    ('truecommand.config', 'TRUECOMMAND_READ', True, False),
    ('truecommand.config', 'TRUECOMMAND_WRITE', True, False),
    ('truecommand.connected', 'TRUECOMMAND_READ', True, False),
    ('truecommand.connected', 'TRUECOMMAND_WRITE', True, False),
    ('truecommand.update', 'TRUECOMMAND_READ', False, True),
    ('truecommand.update', 'TRUECOMMAND_WRITE', True, True),
])
def test_truecommand_read_and_write_role(endpoint, role, should_work, valid_role_exception):
    common_checks(
        endpoint, role, should_work, valid_role_exception=valid_role_exception
    )
