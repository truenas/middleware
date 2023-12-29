import pytest

import contextlib
import os

import shutil

from middlewared.client.client import ValidationErrors, ClientException
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.assets.catalog import catalog
from middlewared.test.integration.utils import call

from middlewared.utils import MIDDLEWARE_RUN_DIR

from auto_config import pool_name


TEST_CATALOG_NAME = 'TEST_CATALOG'
TEST_SECOND_CATALOG_NAME = 'TEST_SECOND_CATALOG'
CATALOG_SYNC_TMP_PATH = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-applications', 'catalogs')


@contextlib.contextmanager
def unconfigured_kubernetes():
    call('kubernetes.update', {'pool': None}, job=True)
    shutil.rmtree(CATALOG_SYNC_TMP_PATH, ignore_errors=True)
    try:
        yield call('kubernetes.config')
    finally:
        call('kubernetes.update', {'pool': None}, job=True)


@contextlib.contextmanager
def configured_kubernetes(pool_info):
    call('kubernetes.update', {'pool': pool_info['name']}, job=True)
    try:
        yield call('kubernetes.config')
    finally:
        call('kubernetes.update', {'pool': None}, job=True)


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


def test_create_new_catalog_with_unconfigured_pool():
    with unconfigured_kubernetes():
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


def test_create_new_catalog_with_configured_pool(kubernetes_pool):
    with configured_kubernetes(kubernetes_pool):
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': TEST_CATALOG_NAME,
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'acl-tests'
        }) as catalog_obj:
            assert os.path.exists(catalog_obj['location'])


def test_catalog_sync_with_unconfigured_pool():
    with unconfigured_kubernetes():
        call('catalog.sync_all', job=True)
        assert os.listdir(CATALOG_SYNC_TMP_PATH) == ['github_com_truenas_charts_git_master']
        with pytest.raises(ClientException) as ve:
            call('catalog.sync', TEST_SECOND_CATALOG_NAME, job=True)

        assert ve.value.error == '[EFAULT] Cannot sync non-official catalogs when apps' \
                                 ' are not configured or catalog dataset is not mounted'


def test_catalog_sync_with_configured_pool(kubernetes_pool):
    with configured_kubernetes(kubernetes_pool) as k3s_config:
        call('catalog.sync_all', job=True)
        assert set(os.listdir(f'/mnt/{k3s_config["dataset"]}/catalogs')) == {'github_com_truenas_charts_git_master',
                                                                             'github_com_truenas_charts_git_test'}
        assert call('catalog.sync', TEST_SECOND_CATALOG_NAME, job=True) is None
