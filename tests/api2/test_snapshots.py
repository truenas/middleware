import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def common_min_max_txg_snapshot_test(test_min_txg=False, test_max_txg=False):
    assert all(i is False for i in (test_min_txg, test_max_txg)) is False

    with dataset('test') as test_dataset:
        created_snaps = []
        total_snaps = 20
        for i in range(total_snaps):
            created_snaps.append(int(call(
                'zfs.snapshot.create', {'dataset': test_dataset, 'name': f'snap_{i}'}
            )['properties']['createtxg']['value']))

        assert call('zfs.snapshot.query', [['dataset', '=', test_dataset]], {'count': True}) == len(created_snaps)

        for i in range(int(total_snaps / 2) - 1):
            new_list = created_snaps
            extra_args = {}
            if test_min_txg:
                new_list = created_snaps[i:]
                extra_args['min_txg'] = new_list[0]
            if test_max_txg:
                new_list = new_list[:int(len(new_list) / 2)]
                extra_args['max_txg'] = new_list[-1]

            assert call(
                'zfs.snapshot.query', [['dataset', '=', test_dataset]], {'count': True, 'extra': extra_args}
            ) == len(new_list)


def test_min_txg_snapshot_query():
    common_min_max_txg_snapshot_test(True, False)


def test_max_txg_snapshot_query():
    common_min_max_txg_snapshot_test(False, True)


def test_min_max_txg_snapshot_query():
    common_min_max_txg_snapshot_test(True, True)
