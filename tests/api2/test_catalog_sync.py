import contextlib
import os
import pytest

from middlewared.client.client import ClientException, ValidationErrors
from middlewared.test.integration.assets.catalog import catalog
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh

from auto_config import pool_name


MIDDLEWARE_RUN_DIR = '/var/run/middleware'
TEST_CATALOG_NAME = 'TEST_CATALOG'
TEST_SECOND_CATALOG_NAME = 'TEST_SECOND_CATALOG'
CATALOG_SYNC_TMP_PATH = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-applications', 'catalogs')


@contextlib.contextmanager
def unconfigured_kubernetes(k3s_pool):
    call('kubernetes.update', {'pool': None}, job=True)
    ssh(f'rm -rf {CATALOG_SYNC_TMP_PATH}')
    try:
        yield call('kubernetes.config')
    finally:
        call('kubernetes.update', {'pool': k3s_pool['name']}, job=True)


@pytest.fixture(scope='module')
def kubernetes_pool():
    with another_pool() as k3s_pool:
        call('kubernetes.update', {'pool': k3s_pool['name']}, job=True)
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': TEST_SECOND_CATALOG_NAME,
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'test'
        }):
            try:
                yield k3s_pool
            finally:
                call('kubernetes.update', {'pool': pool_name}, job=True)


def test_create_new_catalog_with_unconfigured_pool(kubernetes_pool):
    with unconfigured_kubernetes(kubernetes_pool):
        with pytest.raises(ValidationErrors) as ve:
            with catalog({
                'force': True,
                'preferred_trains': ['tests'],
                'label': TEST_CATALOG_NAME,
                'repository': 'https://github.com/truenas/charts.git',
                'branch': 'acl-tests'
            }):
                pass
        assert ve.value.errors[0].errmsg == 'Catalogs cannot be added until apps pool is configured'
        assert ve.value.errors[0].attribute == 'catalog_create.label'


def test_create_new_catalog_with_configured_pool():
    with catalog({
        'force': True,
        'preferred_trains': ['tests'],
        'label': TEST_CATALOG_NAME,
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'acl-tests'
    }) as catalog_obj:
        assert ssh(f'[ -d {catalog_obj["location"]} ] && echo 0 || echo 1').strip() == '0'


def test_catalog_sync_with_unconfigured_pool(kubernetes_pool):
    with unconfigured_kubernetes(kubernetes_pool):
        call('catalog.sync_all', job=True)
        assert ssh(
            f'ls {CATALOG_SYNC_TMP_PATH}'
        ).strip() == 'github_com_truenas_charts_git_master'
        with pytest.raises(ClientException) as ve:
            call('catalog.sync', TEST_SECOND_CATALOG_NAME, job=True)

        assert ve.value.error == '[EFAULT] Cannot sync non-official catalogs when apps' \
                                 ' are not configured or catalog dataset is not mounted'


def test_catalog_sync_with_configured_pool(kubernetes_pool):
    call('catalog.sync_all', job=True)
    assert set(
        ssh(f'ls /mnt/{kubernetes_pool["name"]}/ix-applications/catalogs').strip().split()
    ) == {'github_com_truenas_charts_git_master', 'github_com_truenas_charts_git_test'}
    assert call('catalog.sync', TEST_SECOND_CATALOG_NAME, job=True) is None
