import pytest

from middlewared.plugins.virt import utils

storage = utils.INCUS_STORAGE

DEFAULT_POOL = 'pool_default'
REGULAR_POOL = 'pool_regular'


@pytest.fixture(scope='function')
def default_storage_pool():
    storage.default_storage_pool = 'pool_default'
    try:
        yield
    finally:
        storage.default_storage_pool = None


def test__init_storage_value():
    assert storage.state is utils.VirtGlobalStatus.INITIALIZING
    assert storage.default_storage_pool is None


@pytest.mark.parametrize('status', utils.VirtGlobalStatus)
def test__setting_storage_state(status):
    storage.state = status
    assert storage.state is status


def test__setting_invalid_storage_status():
    with pytest.raises(TypeError):
        storage.state = 'Canary'


def test_default_storage_pool(default_storage_pool):
    assert utils.storage_pool_to_incus_pool(DEFAULT_POOL) == 'default'
    assert utils.storage_pool_to_incus_pool(REGULAR_POOL) == REGULAR_POOL
    assert utils.incus_pool_to_storage_pool('default') == DEFAULT_POOL
    assert utils.incus_pool_to_storage_pool(REGULAR_POOL) == REGULAR_POOL
