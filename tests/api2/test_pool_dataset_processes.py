import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import another_pool

import os
import sys
sys.path.append(os.getcwd())

pytestmark = pytest.mark.zfs


def test_empty_for_locked_root_dataset():
    with another_pool({"encryption": True, "encryption_options": {"passphrase": "passphrase"}}):
        call("pool.dataset.lock", "test", job=True)
        assert call("pool.dataset.processes", "test") == []
