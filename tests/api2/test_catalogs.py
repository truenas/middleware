import os.path

import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.docker import IX_APPS_CATALOG_PATH


@pytest.fixture(scope='module')
def docker_pool(request):
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


@pytest.mark.dependency(name='docker_setup')
def test_docker_setup(docker_pool):
    config = call('docker.update', {'pool': docker_pool}, job=True)
    assert config['pool'] == docker_pool, config


@pytest.mark.dependency(depends=['docker_setup'])
def test_catalog_synced_properly():
    assert call('catalog.synced') is True


@pytest.mark.dependency(depends=['docker_setup'])
def test_catalog_sync_location():
    assert call('catalog.config')['location'] == IX_APPS_CATALOG_PATH


@pytest.mark.dependency(depends=['docker_setup'])
def test_catalog_location_existence():
    docker_config = call('docker.config')
    assert docker_config['pool'] is not None

    assert call('filesystem.statfs', IX_APPS_CATALOG_PATH)['source'] == os.path.join(
        docker_config['dataset'], 'truenas_catalog'
    )


@pytest.mark.dependency(depends=['docker_setup'])
def test_apps_are_being_reported_after_docker_setup():
    assert call('app.available', [], {'count': True}) != 0


@pytest.mark.dependency(depends=['docker_setup'])
def test_categories_are_being_reported():
    assert len(call('app.categories')) != 0


@pytest.mark.dependency(depends=['docker_setup'])
def test_app_version_details():
    app_details = call('catalog.get_app_details', 'plex', {'train': 'stable'})
    assert app_details['name'] == 'plex', app_details

    assert len(app_details['versions']) != 0, app_details


@pytest.mark.dependency(depends=['docker_setup'])
def test_unconfigure_apps_after_setup():
    config = call('docker.update', {'pool': None}, job=True)
    assert config['pool'] is None, config
