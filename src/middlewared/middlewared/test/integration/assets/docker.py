import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def docker(pool: dict):
    docker_config = call('docker.update', {'pool': pool['name']}, job=True)
    assert docker_config['pool'] == pool['name'], docker_config
    try:
        yield docker_config
    finally:
        docker_config = call(
            'docker.update', {'pool': None, 'address_pools': [{'base': '172.17.0.0/12', 'size': 24}]}, job=True
        )
        assert docker_config['pool'] is None, docker_config
