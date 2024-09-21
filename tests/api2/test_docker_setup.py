import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import another_pool


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool() as pool:
        yield pool['name']


def test_docker_setup(docker_pool):
    docker_config = call('docker.update', {'pool': docker_pool}, job=True)
    assert docker_config['pool'] == docker_pool, docker_config


def test_unset_docker_pool(docker_pool):
    docker_config = call('docker.update', {'pool': None}, job=True)
    assert docker_config['pool'] is None, docker_config
