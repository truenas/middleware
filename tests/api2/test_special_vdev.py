import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


POOL_NAME = 'test_special_vdev_pool'


def test_multiple_special_vdevs_same_type():
    """
    Test that multiple special vdevs of the same type can be created.
    This validates: "The metadata vdev type can have more than 1 top-level vdev."
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 8:
        pytest.skip('Insufficient number of disks to perform this test')

    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'data': [{
                'type': 'MIRROR',
                'disks': [unused_disks[0]['name'], unused_disks[1]['name']]
            }],
            'special': [
                {
                    'type': 'RAIDZ1',
                    'disks': [unused_disks[2]['name'], unused_disks[3]['name'], unused_disks[4]['name']]
                },
                {
                    'type': 'RAIDZ1',
                    'disks': [unused_disks[5]['name'], unused_disks[6]['name'], unused_disks[7]['name']]
                }
            ]
        },
        'allow_duplicate_serials': True,
    }) as pool:
        # Verify both special vdevs exist
        assert len(pool['topology']['special']) == 2
        assert pool['topology']['special'][0]['type'].upper() == 'RAIDZ1'
        assert pool['topology']['special'][1]['type'].upper() == 'RAIDZ1'


def test_special_vdev_mixed_types_is_allowed():
    """
    Special vdevs may mix types (e.g. MIRROR + RAIDZ1). truenas_pylibzfs applies
    no same-type rule to the special class, so middleware must not either.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 7:
        pytest.skip('Insufficient number of disks to perform this test')

    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'data': [{
                'type': 'MIRROR',
                'disks': [unused_disks[0]['name'], unused_disks[1]['name']]
            }],
            'special': [
                {
                    'type': 'RAIDZ1',
                    'disks': [unused_disks[2]['name'], unused_disks[3]['name'], unused_disks[4]['name']]
                },
                {
                    'type': 'MIRROR',
                    'disks': [unused_disks[5]['name'], unused_disks[6]['name']]
                }
            ]
        },
        'allow_duplicate_serials': True,
    }) as pool:
        assert len(pool['topology']['special']) == 2
        assert {v['type'].upper() for v in pool['topology']['special']} == {'RAIDZ1', 'MIRROR'}


def test_special_vdev_draid_is_rejected():
    """
    dRAID is not permitted for special vdevs (matching truenas_pylibzfs). The
    special class only accepts MIRROR/RAIDZ/STRIPE, so a DRAID type is rejected
    during pool create validation.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 5:
        pytest.skip('Insufficient number of disks to perform this test')

    with pytest.raises(ValidationErrors) as ve:
        call('pool.create', {
            'name': POOL_NAME,
            'topology': {
                'data': [{
                    'type': 'MIRROR',
                    'disks': [unused_disks[0]['name'], unused_disks[1]['name']]
                }],
                'special': [{
                    'type': 'DRAID1',
                    'disks': [disk['name'] for disk in unused_disks[2:5]],
                }]
            },
            'allow_duplicate_serials': True,
        }, job=True)

    assert ve.value.errors[0].attribute == 'pool_create.topology.special.0.type'
    assert 'dRAID is not supported for special vdevs' in ve.value.errors[0].errmsg


def test_non_redundant_special_on_redundant_data_is_rejected():
    """
    A non-redundant (STRIPE) special vdev is not allowed when the data class is
    redundant, since losing the special vdev would be fatal to the pool. This
    matches the redundancy floor enforced by truenas_pylibzfs.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 3:
        pytest.skip('Insufficient number of disks to perform this test')

    with pytest.raises(ValidationErrors) as ve:
        call('pool.create', {
            'name': POOL_NAME,
            'topology': {
                'data': [{
                    'type': 'MIRROR',
                    'disks': [unused_disks[0]['name'], unused_disks[1]['name']]
                }],
                'special': [{
                    'type': 'STRIPE',
                    'disks': [unused_disks[2]['name']]
                }]
            },
            'allow_duplicate_serials': True,
        }, job=True)

    assert ve.value.errors[0].attribute == 'pool_create.topology.special.0.type'
    assert 'no redundancy' in ve.value.errors[0].errmsg


def test_non_redundant_special_on_striped_data_is_allowed():
    """
    When the data class is not redundant (STRIPE), the redundancy floor does not
    apply, so a non-redundant special vdev is permitted.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 2:
        pytest.skip('Insufficient number of disks to perform this test')

    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'data': [{
                'type': 'STRIPE',
                'disks': [unused_disks[0]['name']]
            }],
            'special': [{
                'type': 'STRIPE',
                'disks': [unused_disks[1]['name']]
            }]
        },
        'allow_duplicate_serials': True,
    }) as pool:
        assert len(pool['topology']['special']) == 1


def test_dedicated_spares_coexist_with_draid_data():
    """
    Dedicated spares may coexist with a dRAID vdev. dRAID is not permitted for
    special vdevs, so this exercises the data class.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 4:
        pytest.skip('Insufficient number of disks to perform this test')

    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'data': [{
                'type': 'DRAID1',
                'disks': [unused_disks[0]['name'], unused_disks[1]['name'], unused_disks[2]['name']],
                'draid_spare_disks': 0,
            }],
            'spares': [unused_disks[3]['name']]
        },
        'allow_duplicate_serials': True,
    }) as pool:
        # The combination is accepted and the dedicated spare is present.
        assert len(pool['topology']['spare']) == 1
        assert pool['topology']['data'][0]['name'].startswith('draid1:')
