import contextlib
import errno
import re
import time

from truenas_api_client import ClientException

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call

CATALOG_SYNC_ATTEMPTS = 4
CATALOG_SYNC_RETRY_DELAY = 10
CATALOG_SYNC_NETWORK_ERRORS = (
    'DNS resolution failed',
    'Could not resolve host',
)


def is_catalog_network_error(exc: Exception) -> bool:
    return any(re.search(pattern, str(exc)) for pattern in CATALOG_SYNC_NETWORK_ERRORS)


def wait_for_catalog_sync(ignore_network_failure: bool = False):
    for job in call('core.get_jobs', [['method', '=', 'catalog.sync'], ['state', 'in', ['WAITING', 'RUNNING']]]):
        try:
            call('core.job_wait', job['id'], job=True)
        except ClientException as e:
            if not ignore_network_failure or not is_catalog_network_error(e):
                raise


def sync_catalog():
    for attempt in range(1, CATALOG_SYNC_ATTEMPTS + 1):
        # A pool change can attach to a sync still cloning the previous location and leave the new one empty
        wait_for_catalog_sync(ignore_network_failure=True)
        try:
            call('catalog.sync', job=True)
            return
        except CallError as e:
            if e.errno != errno.EBUSY:
                raise
        except ClientException as e:
            if attempt == CATALOG_SYNC_ATTEMPTS or not is_catalog_network_error(e):
                raise
            time.sleep(CATALOG_SYNC_RETRY_DELAY)

    raise CallError(f'Catalog did not sync after {CATALOG_SYNC_ATTEMPTS} attempts')


@contextlib.contextmanager
def docker(pool: dict):
    docker_config = call('docker.update', {'pool': pool['name']}, job=True)
    assert docker_config['pool'] == pool['name'], docker_config
    try:
        sync_catalog()
        yield docker_config
    finally:
        docker_config = call(
            'docker.update', {
                'pool': None, 'address_pools': [
                    {'base': '172.17.0.0/12', 'size': 24}, {'base': 'fdd0::/48', 'size': 64}
                ]
            }, job=True
        )
        assert docker_config['pool'] is None, docker_config
