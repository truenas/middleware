import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.docker import IX_APPS_MOUNT_PATH


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool() as pool:
        yield pool['name']


@pytest.mark.dependency(name='unconfigure_apps')
def test_unconfigure_apps():
    config = call('docker.update', {'pool': None}, job=True)
    assert config['pool'] is None, config


@pytest.mark.dependency(depends=['unconfigure_apps'])
def test_catalog_sync():
    call('catalog.sync', job=True)
    assert call('catalog.synced') is True


@pytest.mark.dependency(depends=['unconfigure_apps'])
def test_catalog_cloned_location():
    config = call('catalog.config')
    assert config['location'] == '/var/run/middleware/ix-apps/catalogs', config


@pytest.mark.dependency(depends=['unconfigure_apps'])
def test_apps_are_being_reported():
    assert call('app.available', [], {'count': True}) != 0
