import contextlib
import os
import pytest

from middlewared.client.client import ClientException, ValidationErrors
from middlewared.test.integration.assets.catalog import catalog
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, fail, ssh, mock


MIDDLEWARE_RUN_DIR = '/var/run/middleware'
TEST_CATALOG_NAME = 'TEST_CATALOG'
TEST_SECOND_CATALOG_NAME = 'TEST_SECOND_CATALOG'
CATALOG_SYNC_TMP_PATH = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-applications', 'catalogs')
pytestmark = pytest.mark.apps


@contextlib.contextmanager
def unconfigured_kubernetes():
    with mock('kubernetes.config', return_value={'dataset': None, 'pool': None, 'passthrough_mode': False}):
        ssh(f'rm -rf {CATALOG_SYNC_TMP_PATH}')
        yield


@contextlib.contextmanager
def configured_kubernetes(k3s_pool_name):
    with mock(
        'kubernetes.config', return_value={
            'dataset': f'{k3s_pool_name}/applications',
            'pool': k3s_pool_name,
            'passthrough_mode': False,
        }
    ):
        yield


@pytest.fixture(scope='module')
def kubernetes_pool():
    with another_pool() as k3s_pool:
        call('pool.dataset.create', {'name': f'{k3s_pool["name"]}/applications'})
        call('pool.dataset.create', {'name': f'{k3s_pool["name"]}/applications/catalogs'})
        with configured_kubernetes(k3s_pool['name']):
            catalog_data = call('catalog.create', {
                'force': True,
                'preferred_trains': ['tests'],
                'label': TEST_CATALOG_NAME,
                'repository': 'https://github.com/truenas/charts.git',
                'branch': 'acl-tests'
            }, job=True)
        try:
            yield k3s_pool
        finally:
            call('pool.dataset.delete', f'{k3s_pool["name"]}/applications/catalogs', {'recursive': True})
            call('catalog.delete', catalog_data['id'])


def test_create_new_catalog_with_configured_pool(kubernetes_pool):
    with configured_kubernetes(kubernetes_pool['name']):
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': TEST_SECOND_CATALOG_NAME,
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'test'
        }) as cat:
            assert ssh(
                f'[ -d {cat["location"]} ]'
                f' && echo 0 || echo 1'
            ).strip() == '0'


def test_catalog_sync_with_configured_pool(kubernetes_pool):
    with configured_kubernetes(kubernetes_pool['name']):
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': TEST_SECOND_CATALOG_NAME,
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'test'
        }):
            call('catalog.sync_all', job=True)
            assert set(
                ssh(f'ls /mnt/{kubernetes_pool["name"]}/applications/catalogs').strip().split()
            ) == {
                'github_com_truenas_charts_git_master',
                'github_com_truenas_charts_git_test',
                'github_com_truenas_charts_git_acl-tests',
            }
            assert call('catalog.sync', TEST_SECOND_CATALOG_NAME, job=True) is None


def test_create_new_catalog_with_unconfigured_pool():
    with unconfigured_kubernetes():
        with pytest.raises(ValidationErrors) as ve:
            with catalog({
                'force': True,
                'preferred_trains': ['tests'],
                'label': TEST_SECOND_CATALOG_NAME,
                'repository': 'https://github.com/truenas/charts.git',
                'branch': 'test'
            }):
                pass
        assert ve.value.errors[0].errmsg == 'Catalogs cannot be added until apps pool is configured'
        assert ve.value.errors[0].attribute == 'catalog_create.label'


def test_catalog_sync_with_unconfigured_pool():
    with unconfigured_kubernetes():
        call('catalog.sync_all', job=True)
        assert ssh(
            f'ls {CATALOG_SYNC_TMP_PATH}'
        ).strip() == 'github_com_truenas_charts_git_master'
        with pytest.raises(ClientException) as ve:
            call('catalog.sync', TEST_CATALOG_NAME, job=True)

        assert ve.value.error == '[EFAULT] Cannot sync non-official catalogs when apps' \
                                 ' are not configured or catalog dataset is not mounted'
