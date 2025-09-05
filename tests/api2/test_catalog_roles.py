import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('method, role, valid_role, valid_role_exception', (
    ('catalog.get_app_details', 'CATALOG_READ', True, True),
    ('catalog.get_app_details', 'CATALOG_WRITE', True, True),
    ('catalog.get_app_details', 'DOCKER_READ', False, False),
    ('app.latest', 'CATALOG_READ', True, False),
    ('app.latest', 'CATALOG_WRITE', True, False),
    ('app.latest', 'APPS_WRITE', True, False),
    ('app.available', 'CATALOG_READ', True, False),
    ('app.available', 'CATALOG_WRITE', True, False),
    ('app.available', 'APPS_WRITE', True, False),
    ('app.categories', 'CATALOG_READ', True, False),
    ('app.categories', 'CATALOG_WRITE', True, False),
    ('app.categories', 'APPS_WRITE', True, False),
    ('app.similar', 'CATALOG_READ', True, True),
    ('app.similar', 'CATALOG_WRITE', True, True),
    ('app.similar', 'APPS_WRITE', True, True),
    ('catalog.apps', 'CATALOG_READ', True, False),
    ('catalog.apps', 'CATALOG_WRITE', True, False),
    ('catalog.apps', 'DOCKER_READ', False, True),
    ('catalog.sync', 'CATALOG_READ', False, False),
    ('catalog.sync', 'CATALOG_WRITE', True, False),
    ('catalog.update', 'CATALOG_READ', False, True),
    ('catalog.update', 'CATALOG_WRITE', True, True),

))
def test_apps_roles(unprivileged_user_fixture, method, role, valid_role, valid_role_exception):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=valid_role_exception)
