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


def common_min_max_txg_snapshot_test(min_txg_test):
    with dataset('test') as test_dataset:
        created_snaps = []
        total_snaps = 10
        for i in range(total_snaps):
            created_snaps.append(int(call(
                'zfs.snapshot.create', {'dataset': test_dataset, 'name': f'snap_{i}'}
            )['properties']['createtxg']['value']))

        assert call('zfs.snapshot.query', [['dataset', '=', test_dataset]], {'count': True}) == len(created_snaps)

        for i in (2, 3, 4):
            split = int(total_snaps / i)
            new_list = created_snaps[split:] if min_txg_test else created_snaps[:split]
            assert call('zfs.snapshot.query', [['dataset', '=', test_dataset]], {'count': True, 'extra': {
                'min_txg' if min_txg_test else 'max_txg': new_list[0 if min_txg_test else -1],
            }}) == len(new_list)


def test_min_txg_snapshot_query():
    common_min_max_txg_snapshot_test(True)


def test_max_txg_snapshot_query():
    common_min_max_txg_snapshot_test(False)
