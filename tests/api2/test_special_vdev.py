import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


POOL_NAME = 'test_special_vdev_pool'


def test_draid_special_vdev_gets_correct_allocation_bias():
    """
    CRITICAL: Test that DRAID special vdevs get VDEV_ALLOC_BIAS_SPECIAL.
    This validates the special_vdev flag flow: middleware → py-libzfs.
    Without this flag, DRAID special vdevs would be created as data vdevs.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 5:
        pytest.skip('Insufficient number of disks to perform this test')

    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'data': [{
                'type': 'MIRROR',
                'disks': [unused_disks[0]['name'], unused_disks[1]['name']]
            }],
            'special': [{
                'type': 'DRAID1',
                'disks': [disk['name'] for disk in unused_disks[2:5]],
                'draid_spare_disks': 0,
            }]
        },
        'allow_duplicate_serials': True,
    }) as pool:
        # Verify DRAID special vdev exists in topology
        assert len(pool['topology']['special']) == 1
        assert pool['topology']['special'][0]['name'].startswith('draid1:')

        # Verify pool is detected as DRAID pool (tests is_draid_pool includes special)
        assert call('pool.is_draid_pool', pool['name']) is True


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


def test_special_vdev_mixed_types_should_fail():
    """
    Test middleware validation: mixing different vdev types in special topology fails.
    This is middleware-enforced (pool.py:308-314), not ZFS.
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 7:
        pytest.skip('Insufficient number of disks to perform this test')

    with pytest.raises(ValidationErrors) as ve:
        call('pool.create', {
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
        }, job=True)

    # Verify middleware validation caught it
    assert ve.value.errors[0].attribute == 'pool_create.topology.special.1.type'
    assert 'You are not allowed to create a pool with different special vdev types' in ve.value.errors[0].errmsg
    assert 'RAIDZ1' in ve.value.errors[0].errmsg and 'MIRROR' in ve.value.errors[0].errmsg


def test_draid_special_with_dedicated_spares_should_fail():
    """
    Test middleware validation: DRAID special vdevs cannot be used with dedicated spares.
    This validates the fix at pool.py:302-306 (spare → spares).
    """
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 6:
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
                    'disks': [unused_disks[2]['name'], unused_disks[3]['name'], unused_disks[4]['name']],
                    'draid_spare_disks': 0,
                }],
                'spares': [unused_disks[5]['name']]
            },
            'allow_duplicate_serials': True,
        }, job=True)

    # Verify middleware validation caught it
    assert ve.value.errors[0].attribute == 'pool_create.topology.spares'
    assert 'Dedicated spare disks should not be used with dRAID' in ve.value.errors[0].errmsg
