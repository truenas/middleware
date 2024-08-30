import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('method, role, valid_role, valid_role_exception', (
    ('app.image.query', 'APPS_READ', True, False),
    ('app.image.query', 'APPS_WRITE', True, False),
    ('app.image.query', 'DOCKER_READ', False, False),
    ('app.image.pull', 'APPS_READ', False, False),
    ('app.image.pull', 'APPS_WRITE', True, False),
    ('app.image.delete', 'APPS_READ', False, False),
    ('app.image.delete', 'APPS_WRITE', True, True),
))
def test_apps_roles(unprivileged_user_fixture, method, role, valid_role, valid_role_exception):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=valid_role_exception)
