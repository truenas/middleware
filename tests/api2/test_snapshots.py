import errno

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def common_min_max_txg_snapshot_test(test_min_txg=False, test_max_txg=False):
    assert all(i is False for i in (test_min_txg, test_max_txg)) is False

    with dataset('test') as test_dataset:
        created_snaps = []
        total_snaps = 20
        for i in range(total_snaps):
            created_snaps.append(int(call(
                'pool.snapshot.create', {'dataset': test_dataset, 'name': f'snap_{i}'}
            )['properties']['createtxg']['value']))

        assert call('pool.snapshot.query', [['dataset', '=', test_dataset]], {'count': True}) == len(created_snaps)

        for i in range(total_snaps // 2 - 1):
            new_list = created_snaps
            extra_args = {}
            if test_min_txg:
                new_list = created_snaps[i:]
                extra_args['min_txg'] = new_list[0]
            if test_max_txg:
                new_list = new_list[:len(new_list) // 2]
                extra_args['max_txg'] = new_list[-1]

            assert call(
                'pool.snapshot.query', [['dataset', '=', test_dataset]], {'count': True, 'extra': extra_args}
            ) == len(new_list)


def test_min_txg_snapshot_query():
    common_min_max_txg_snapshot_test(True, False)


def test_max_txg_snapshot_query():
    common_min_max_txg_snapshot_test(False, True)


def test_min_max_txg_snapshot_query():
    common_min_max_txg_snapshot_test(True, True)


def test_already_exists():
    with dataset('test') as test_dataset:
        call('pool.snapshot.create', {'dataset': test_dataset, 'name': 'snap'})
        with pytest.raises(ValidationError) as ve:
            call('pool.snapshot.create', {'dataset': test_dataset, 'name': 'snap'})

        assert ve.value.errno == errno.EEXIST
