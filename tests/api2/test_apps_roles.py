import contextlib
import errno
import pytest

from pytest_dependency import depends
from time import sleep

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def official_chart_release(wait_for_active_status=False):
    release_name = 'tftpd-hpa'
    payload = {
        'catalog': 'TRUENAS',
        'item': 'tftpd-hpa',
        'release_name': release_name,
        'train': 'community',
    }
    chart_release = call('chart.release.create', payload, job=True)
    if wait_for_active_status:
        timeout = 60
        while timeout >= 0 and call('chart.release.get_instance', release_name)['status'] != 'ACTIVE':
            sleep(10)
            timeout -= 10

    try:
        yield chart_release
    finally:
        call('chart.release.delete', 'tftpd-hpa', job=True)


def test_app_readonly_role(request):
    depends(request, ['setup_kubernetes'], scope='session')
    with unprivileged_user_client(['READONLY_ADMIN']) as c:
        c.call('app.categories')


@pytest.mark.parametrize('role,endpoint,payload,job,should_work', [
    ('CATALOG_READ', 'app.latest', [], False, True),
    ('CATALOG_READ', 'app.available', [], False, True),
    ('CATALOG_READ', 'app.categories', [], False, True),
    ('APPS_READ', 'app.latest', [], False, True),
    ('APPS_READ', 'app.available', [], False, True),
    ('APPS_READ', 'app.categories', [], False, True),
    ('CATALOG_READ', 'app.similar', ['searxng', 'TRUENAS', 'community'], False, True),
    ('CATALOG_WRITE', 'app.similar', ['searxng', 'TRUENAS', 'community'], False, True),
    ('CATALOG_READ', 'catalog.sync_all', [], True, False),
    ('CATALOG_READ', 'catalog.sync', ['TRUENAS'], True, False),
    ('CATALOG_READ', 'catalog.validate', ['TRUENAS'], True, False),
    ('CATALOG_WRITE', 'catalog.sync_all', [], True, True),
    ('CATALOG_WRITE', 'catalog.sync', ['TRUENAS'], True, True),
    ('CATALOG_WRITE', 'catalog.validate', ['TRUENAS'], True, True),
    ('CATALOG_READ', 'catalog.get_item_details', ['searxng', {'catalog': 'TRUENAS', 'train': 'community'}], False, True),
    ('CATALOG_READ', 'catalog.items', ['TRUENAS'], False, True),
    ('CATALOG_WRITE', 'catalog.items', ['TRUENAS'], False, True),
])
def test_catalog_read_and_write_role(request, role, endpoint, payload, job, should_work):
    depends(request, ['setup_kubernetes'], scope='session')
    with unprivileged_user_client(roles=[role]) as c:
        if should_work:
            c.call(endpoint, *payload, job=job)
        else:
            with pytest.raises(ClientException) as ve:
                c.call(endpoint, *payload, job=job)
            assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize('role,endpoint,job,should_work', [
    ('APPS_READ', 'chart.release.used_ports', False, True),
    ('APPS_READ', 'container.image.dockerhub_rate_limit', False, True),
    ('APPS_WRITE', 'container.image.dockerhub_rate_limit', False, True),
    ('APPS_READ', 'container.prune', True, False),
    ('APPS_WRITE', 'container.prune', True, True),
])
def test_apps_read_and_write_roles(request, role, endpoint, job, should_work):
    depends(request, ['setup_kubernetes'], scope='session')
    with official_chart_release():
        with unprivileged_user_client(roles=[role]) as c:
            if should_work:
                c.call(endpoint, job=job)
            else:
                with pytest.raises(ClientException) as ve:
                    c.call(endpoint, job=job)
                assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize('role,endpoint,job,should_work,expected_error,wait_for_active_status', [
    ('APPS_READ', 'chart.release.pod_status', False, True, False, False),
    ('APPS_WRITE', 'chart.release.pod_status', False, True, False, False),
    ('APPS_READ', 'chart.release.upgrade_summary', False, True, True, False),
    ('APPS_READ', 'chart.release.redeploy', True, False, False, True),
    ('APPS_WRITE', 'chart.release.redeploy', True, True, False, True),
    ('APPS_READ', 'chart.release.upgrade', True, False, False, False),
    ('APPS_WRITE', 'chart.release.upgrade', True, True, True, False),
])
def test_apps_read_and_write_roles_with_params(
    request, role, endpoint, job, should_work, expected_error, wait_for_active_status,
):
    depends(request, ['setup_kubernetes'], scope='session')
    with official_chart_release(wait_for_active_status) as chart_release:
        with unprivileged_user_client(roles=[role]) as c:
            if should_work:
                if expected_error:
                    with pytest.raises(Exception) as ve:
                        c.call(endpoint, chart_release['name'], job=job)
                    assert ve.value.errno != errno.EACCES
                else:
                    c.call(endpoint, chart_release['name'], job=job)

            else:
                with pytest.raises(ClientException) as ve:
                    c.call(endpoint, chart_release['name'], job=job)
                assert ve.value.errno == errno.EACCES


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
def test_kubernetes_read_and_write_roles(request, role, endpoint, job, should_work):
    depends(request, ['setup_kubernetes'], scope='session')
    with unprivileged_user_client(roles=[role]) as c:
        if should_work:
            c.call(endpoint, job=job)
        else:
            with pytest.raises(ClientException) as ve:
                c.call(endpoint, job=job)
            assert ve.value.errno == errno.EACCES
