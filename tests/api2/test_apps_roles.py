import pytest

from middlewared.test.integration.assets.roles import common_checks


def test_app_readonly_role(unprivileged_user_fixture):
    common_checks(unprivileged_user_fixture, 'app.categories', 'READONLY_ADMIN', True, valid_role_exception=False)


@pytest.mark.parametrize('role,endpoint,payload,job,should_work,valid_role_exception,is_return_type_none', [
    ('CATALOG_READ', 'app.latest', [], False, True, False, False),
    ('CATALOG_READ', 'app.available', [], False, True, False, False),
    ('CATALOG_READ', 'app.categories', [], False, True, False, False),
    ('APPS_READ', 'app.latest', [], False, True, False, False),
    ('APPS_READ', 'app.available', [], False, True, False, False),
    ('APPS_READ', 'app.categories', [], False, True, False, False),
    ('CATALOG_READ', 'app.similar', [], False, True, True, False),
    ('CATALOG_WRITE', 'app.similar', [], False, True, True, False),
    ('CATALOG_READ', 'catalog.sync_all', [], True, False, False, True),
    ('CATALOG_READ', 'catalog.sync', [], True, False, True, True),
    ('CATALOG_READ', 'catalog.validate', [], True, False, True, False),
    ('CATALOG_WRITE', 'catalog.sync_all', [], True, True, False, True),
    ('CATALOG_WRITE', 'catalog.sync', [], True, True, True, True),
    ('CATALOG_WRITE', 'catalog.validate', [], True, True, True, False),
    ('CATALOG_READ', 'catalog.get_item_details', [], False, True, True, False),
    ('CATALOG_READ', 'catalog.items', [], False, True, True, False),
    ('CATALOG_WRITE', 'catalog.items', [], False, True, True, False),
])
def test_catalog_read_and_write_role(
    unprivileged_user_fixture, role, endpoint, payload, job, should_work, valid_role_exception, is_return_type_none
):
    common_checks(
        unprivileged_user_fixture, endpoint, role, should_work, is_return_type_none=is_return_type_none,
        valid_role_exception=valid_role_exception, method_args=payload, method_kwargs={'job': job}
    )


@pytest.mark.parametrize('role,endpoint,job,should_work', [
    ('APPS_READ', 'chart.release.used_ports', False, True),
    ('APPS_READ', 'container.image.dockerhub_rate_limit', False, True),
    ('APPS_WRITE', 'container.image.dockerhub_rate_limit', False, True),
    ('APPS_READ', 'container.prune', True, False),
    ('APPS_WRITE', 'container.prune', True, True),
])
def test_apps_read_and_write_roles(unprivileged_user_fixture, role, endpoint, job, should_work):
    common_checks(
        unprivileged_user_fixture, endpoint, role, should_work, valid_role_exception=False, method_kwargs={'job': job}
    )


@pytest.mark.parametrize('role,endpoint,job,should_work', [
    ('APPS_READ', 'chart.release.pod_status', False, True),
    ('APPS_WRITE', 'chart.release.pod_status', False, True),
    ('APPS_READ', 'chart.release.upgrade_summary', False, True),
    ('APPS_READ', 'chart.release.redeploy', True, False),
    ('APPS_WRITE', 'chart.release.redeploy', True, True),
    ('APPS_READ', 'chart.release.upgrade', True, False),
    ('APPS_WRITE', 'chart.release.upgrade', True, True),
])
def test_apps_read_and_write_roles_with_params(unprivileged_user_fixture, role, endpoint, job, should_work):
    common_checks(unprivileged_user_fixture, endpoint, role, should_work, method_kwargs={'job': job})


@pytest.mark.parametrize('role,endpoint,job,should_work', [
    ('KUBERNETES_READ', 'kubernetes.backup_chart_releases', True, False),
    ('KUBERNETES_WRITE', 'kubernetes.backup_chart_releases', True, True),
    ('KUBERNETES_READ', 'kubernetes.list_backups', False, True),
    ('KUBERNETES_WRITE', 'kubernetes.list_backups', False, True),
    ('KUBERNETES_READ', 'kubernetes.status', False, True),
    ('KUBERNETES_READ', 'kubernetes.node_ip', False, True),
    ('KUBERNETES_READ', 'kubernetes.events', False, True),
    ('KUBERNETES_WRITE', 'kubernetes.events', False, True),
])
def test_kubernetes_read_and_write_roles(unprivileged_user_fixture, role, endpoint, job, should_work):
    common_checks(
        unprivileged_user_fixture, endpoint, role, should_work, valid_role_exception=False, method_kwargs={'job': job}
    )
