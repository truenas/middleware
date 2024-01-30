import textwrap

import pytest

from middlewared.test.integration.utils import call, mock
from middlewared.test.integration.assets.pool import dataset

import os
import sys
sys.path.append(os.getcwd())

pytestmark = pytest.mark.zfs


def test_empty_for_locked_root_dataset():
    with dataset("test_pool_dataset_snapshot_count") as ds:
        for i in range(7):
            call("zfs.snapshot.create", {"dataset": ds, "name": f"snap-{i}"})

        with mock("zfs.snapshot.query", textwrap.dedent("""\
            def mock(self, *args):
                raise Exception("Should not be called")
        """)):
            assert call("pool.dataset.snapshot_count", ds) == 7
