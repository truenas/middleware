import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call

from auto_config import ha


pytestmark = [
    pytest.mark.skipif(ha, reason='Skipping for HA testing due to less disks'),
]


@pytest.fixture(scope='module')
def check_unused_disks():
    if len(call('disk.get_unused')) < 4:
        pytest.skip('Insufficient number of disks to perform these tests')


@pytest.fixture(scope='module')
def draid_pool():
    unused_disks = call('disk.get_unused')
    with another_pool({
        'name': 'test_draid_pool',
        'topology': {
            'data': [{
                'disks': [disk['name'] for disk in unused_disks[:2]],
                'type': 'DRAID1',
                'draid_data_disks': 1
            }],
        },
        'allow_duplicate_serials': True,
    }) as pool_name:
        yield pool_name


@pytest.fixture(scope='module')
def mirror_pool():
    unused_disks = call('disk.get_unused')
    with another_pool({
        'name': 'test_mirror_pool',
        'topology': {
            'data': [{
                'disks': [disk['name'] for disk in unused_disks[:2]],
                'type': 'MIRROR',
            }],
        },
        'allow_duplicate_serials': True,
    }) as pool_name:
        yield pool_name


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'record_size', ['1M']
)
def test_draid_pool_default_record_size(draid_pool, record_size):
    assert call('pool.dataset.get_instance', draid_pool['name'])['recordsize']['value'] == record_size


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'record_size', ['128K']
)
def test_non_draid_pool_default_record_size(mirror_pool, record_size):
    assert call('pool.dataset.get_instance', mirror_pool['name'])['recordsize']['value'] == record_size


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'update_recordsize, validation_error', [
        ('512K', False),
        ('256K', False),
        ('128K', False),
        ('2M', False),
        ('512', True),
        ('4K', True),
        ('64K', True),
    ]
)
def test_draid_root_dataset_valid_recordsize(draid_pool, update_recordsize, validation_error):
    if not validation_error:
        assert call(
            'pool.dataset.update', draid_pool['name'], {'recordsize': update_recordsize}
        )['recordsize']['value'] == update_recordsize
    else:
        with pytest.raises(ValidationErrors) as ve:
            call('pool.dataset.update', draid_pool['name'], {'recordsize': update_recordsize})

        assert ve.value.errors[0].attribute == 'pool_dataset_update.recordsize'
        assert ve.value.errors[0].errmsg == f"'{update_recordsize}' is an invalid recordsize."


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'update_recordsize', ['512K', '256K', '128K', '2M', '512', '4K', '64K']
)
def test_non_draid_root_dataset_valid_recordsize(mirror_pool, update_recordsize):
    assert call(
        'pool.dataset.update', mirror_pool['name'], {'recordsize': update_recordsize}
    )['recordsize']['value'] == update_recordsize


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'recordsize, validation_error', [
        ('512K', False),
        ('256K', False),
        ('128K', False),
        ('2M', False),
        ('512', True),
        ('4K', True),
        ('64K', True),
    ]
)
def test_draid_dataset_valid_recordsize(draid_pool, recordsize, validation_error):
    if not validation_error:
        assert call(
            'pool.dataset.create', {'name': f'{draid_pool["name"]}/test_dataset_{recordsize}', 'recordsize': recordsize}
        )['recordsize']['value'] == recordsize
    else:
        with pytest.raises(ValidationErrors) as ve:
            call('pool.dataset.create', {'name': f'{draid_pool["name"]}/test_dataset_{recordsize}',
                                         'recordsize': recordsize})

        assert ve.value.errors[0].attribute == 'pool_dataset_create.recordsize'
        assert ve.value.errors[0].errmsg == f"'{recordsize}' is an invalid recordsize."


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'recordsize', ['512K', '256K', '128K', '2M', '512', '4K', '64K']
)
def test_non_draid_dataset_valid_recordsize(mirror_pool, recordsize):
    assert call(
        'pool.dataset.create', {'name': f'{mirror_pool["name"]}/test_dataset_{recordsize}', 'recordsize': recordsize}
    )['recordsize']['value'] == recordsize


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'blocksize,validation_error', [
        ('16K', True),
        ('32K', False),
    ]
)
def test_draid_zvol_valid_blocksize(draid_pool, blocksize, validation_error):
    if not validation_error:
        assert call(
            'pool.dataset.create', {
                'name': f'{draid_pool["name"]}/test_dataset_{blocksize}', 'volsize': 268468224,
                'volblocksize': blocksize, 'type': 'VOLUME',
            }
        )['volblocksize']['value'] == blocksize
    else:
        with pytest.raises(ValidationErrors) as ve:
            call(
                'pool.dataset.create', {
                    'name': f'{draid_pool["name"]}/test_dataset_{blocksize}', 'volsize': 268468224,
                    'volblocksize': blocksize, 'type': 'VOLUME'
                }
            )

        assert ve.value.errors[0].attribute == 'pool_dataset_create.volblocksize'
        assert ve.value.errors[0].errmsg == 'Volume block size must be greater than or equal to 32K for dRAID pools'


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'blocksize', ['16K', '32K']
)
def test_non_draid_zvol_valid_blocksize(mirror_pool, blocksize):
    assert call(
        'pool.dataset.create', {
            'name': f'{mirror_pool["name"]}/test_dataset_{blocksize}', 'volsize': 268468224,
            'volblocksize': blocksize, 'type': 'VOLUME',
        }
    )['volblocksize']['value'] == blocksize


@pytest.mark.usefixtures('check_unused_disks')
@pytest.mark.parametrize(
    'update_recordsize, default_record_size', [
        ('512K', '1M'),
    ]
)
def test_draid_dataset_default_recordsize(draid_pool, update_recordsize, default_record_size):
    assert call(
        'pool.dataset.update', draid_pool['name'], {'recordsize': update_recordsize}
    )['recordsize']['value'] == update_recordsize

    assert call(
        'pool.dataset.create', {'name': f'{draid_pool["name"]}/test_dataset'}
    )['recordsize']['value'] == default_record_size
