import pytest

from middlewared.client.client import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


POOL_NAME = 'test_draid_pool'


@pytest.mark.parametrize(
    'n_data,n_parity', [
        (1, 1),
        (1, 2),
        (1, 2),
        (2, 2),
        (1, 3),
    ]
)
def test_valid_draid_pool_creation(n_data, n_parity):
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 4:
        pytest.skip('Insufficient number of disk to perform these test')

    children = n_data + n_parity
    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'data': [{
                'disks': [disk['name'] for disk in unused_disks[:children]],
                'type': f'DRAID{n_parity}'
            }],
        },
        'allow_duplicate_serials': True,
    }) as draid:
        assert draid['topology']['data'][0]['name'] == f'draid{n_parity}:{n_data}d:{children}c:0s-0'
        unused_disk_for_update = call('disk.get_unused')
        if len(unused_disk_for_update) >= children:
            draid_pool_updated = call(
                'pool.update', draid['id'], {
                    'topology': {
                        'data': [{
                            'type': f'DRAID{n_parity}',
                            'disks': [disk['name'] for disk in unused_disk_for_update[:children]]
                        }]
                    },
                    'allow_duplicate_serials': True,
                }, job=True)
            assert len(draid_pool_updated['topology']['data']) == 2
            assert draid_pool_updated['topology']['data'][1]['name'] == f'draid{n_parity}:{n_data}d:{children}c:0s-1'


@pytest.mark.parametrize(
    'n_data,n_parity,minimum_disk', [
        (0, 1, 2),
        (0, 2, 3),
        (0, 3, 4),
    ]
)
def test_invalid_draid_pool_creation(n_data, n_parity, minimum_disk):
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 3:
        pytest.skip('Insufficient number of disk to perform these test')

    children = n_data + n_parity

    with pytest.raises(ValidationErrors) as ve:
        call('pool.create', {
            'name': POOL_NAME,
            'topology': {
                'data': [{
                    'disks': [disk['name'] for disk in unused_disks[:children]],
                    'type': f'DRAID{n_parity}',
                }],
            },
            'allow_duplicate_serials': True,
        }, job=True)

    assert ve.value.errors[0].attribute == 'pool_create.topology.data.0.disks'
    assert ve.value.errors[0].errmsg == f'You need at least {minimum_disk} disk(s) for this vdev type.'
