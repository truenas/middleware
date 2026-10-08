import contextlib
import errno

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call


def wait_for_catalog_sync():
    for job in call('core.get_jobs', [['method', '=', 'catalog.sync'], ['state', 'in', ['WAITING', 'RUNNING']]]):
        call('core.job_wait', job['id'], job=True)


def sync_catalog():
    # A pool change can attach to a sync still cloning the previous location and leave the new one empty
    wait_for_catalog_sync()
    try:
        call('catalog.sync', job=True)
    except CallError as e:
        if e.errno != errno.EBUSY:
            raise
        wait_for_catalog_sync()


@contextlib.contextmanager
def docker(pool: dict):
    docker_config = call('docker.update', {'pool': pool['name']}, job=True)
    assert docker_config['pool'] == pool['name'], docker_config
    sync_catalog()
    try:
        yield docker_config
    finally:
        docker_config = call(
            'docker.update', {
                'pool': None, 'address_pools': [
                    {'base': '172.16.0.0/12', 'size': 24}, {'base': 'fdd0::/48', 'size': 64}
                ]
            }, job=True
        )
        assert docker_config['pool'] is None, docker_config
