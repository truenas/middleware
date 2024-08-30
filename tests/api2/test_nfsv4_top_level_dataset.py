import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool


@pytest.fixture(scope='module')
def set_nfsv4_top_level():
    call('pool.dataset.update', pool, {'acltype': 'NFSV4', 'aclmode': 'PASSTHROUGH'})

    try:
        yield
    finally:
        call('pool.dataset.update', pool, {'acltype': 'POSIX', 'aclmode': 'DISCARD'})


def test__acltype_inherit(set_nfsv4_top_level):
    with dataset('v4inherit') as ds:
        entry = call('pool.dataset.query', [['name', '=', ds]], {'get': True})

        assert entry['acltype']['value'] == 'NFSV4'
        assert entry['aclmode']['value'] == 'PASSTHROUGH'
