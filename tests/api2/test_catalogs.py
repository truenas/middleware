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
