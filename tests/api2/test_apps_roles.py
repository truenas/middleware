import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('method, role, valid_role, valid_role_exception', (
    ('app.query', 'APPS_READ', True, False),
    ('app.query', 'APPS_WRITE', True, False),
    ('app.query', 'DOCKER_READ', False, False),
    ('app.config', 'APPS_READ', True, True),
    ('app.config', 'APPS_WRITE', True, True),
    ('app.config', 'DOCKER_READ', False, False),
    ('app.update', 'APPS_READ', False, False),
    ('app.update', 'APPS_WRITE', True, True),
    ('app.create', 'APPS_READ', False, False),
    ('app.create', 'APPS_WRITE', True, True),
    ('app.delete', 'APPS_READ', False, False),
    ('app.delete', 'APPS_WRITE', True, True),
    ('app.convert_to_custom', 'APPS_READ', False, False),
    ('app.convert_to_custom', 'APPS_WRITE', True, True),
))
def test_apps_roles(unprivileged_user_fixture, method, role, valid_role, valid_role_exception):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=valid_role_exception)
