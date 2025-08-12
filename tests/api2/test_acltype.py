import pytest

from auto_config import pool_name
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset


def query_filters(ds_name):
    return [['id', '=', ds_name]], {'get': True, 'extra': {'retrieve_children': False}}


@pytest.fixture(scope='module')
def temp_ds():
    with dataset('test1') as ds:
        yield ds


def test_default_acltype_on_zpool():
    assert 'POSIXACL' in call('filesystem.statfs', f'/mnt/{pool_name}')['flags']


def test_acltype_inheritance(temp_ds):
    tds = call('zfs.resource.query', {'paths': [temp_ds], 'properties': ['acltype']})
    assert tds
    assert tds[0]['properties']['acltype']['raw'] == 'posix'


@pytest.mark.parametrize(
    'change,expected', [
        (
            {'acltype': 'NFSV4', 'aclmode': 'PASSTHROUGH'},
            (('acltype', 'value', 'nfsv4'), ('aclmode', 'value', 'passthrough'), ('aclinherit', 'value', 'passthrough'))
        ),
        (
            {'acltype': 'POSIX', 'aclmode': 'DISCARD'},
            (('acltype', 'value', 'posix'), ('aclmode', 'value', 'discard'), ('aclinherit', 'value', 'discard'))
        ),
    ],
    ids=['NFSV4_PASSTHROUGH', 'POSIX_DISCARD']
)
def test_change_acltype_and_aclmode_to_(temp_ds, change, expected):
    call('pool.dataset.update', temp_ds, change)
    props = call(
        'zfs.resource.query',
        {'paths': [temp_ds], 'properties': ['acltype', 'aclmode', 'aclinherit']}
    )[0]['properties']
    for tkey, skey, value in expected:
        assert props[tkey][skey] == value, props[tkey][skey]
