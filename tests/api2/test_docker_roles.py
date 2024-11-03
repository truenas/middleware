import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('method, role, valid_role, valid_role_exception', (
    ('docker.status', 'DOCKER_READ', True, False),
    ('docker.status', 'DOCKER_WRITE', True, False),
    ('docker.status', 'CATALOG_READ', False, False),
    ('docker.config', 'DOCKER_READ', True, False),
    ('docker.config', 'DOCKER_WRITE', True, False),
    ('docker.config', 'CATALOG_READ', False, False),
    ('docker.nvidia_status', 'DOCKER_READ', True, False),
    ('docker.nvidia_status', 'DOCKER_WRITE', True, False),
    ('docker.nvidia_status', 'CATALOG_READ', False, False),
    ('docker.update', 'DOCKER_READ', False, False),
    ('docker.update', 'DOCKER_WRITE', True, True),
))
def test_apps_roles(unprivileged_user_fixture, method, role, valid_role, valid_role_exception):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=valid_role_exception)
