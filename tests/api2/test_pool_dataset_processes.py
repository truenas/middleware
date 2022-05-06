import contextlib
import time

import pytest

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import dataset, pool, another_pool

import os
import sys
sys.path.append(os.getcwd())
from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_empty_for_locked_root_dataset():
    with another_pool({"encryption": True, "encryption_options": {"passphrase": "passphrase"}}):
        call("pool.dataset.lock", "test", job=True)
        assert call("pool.dataset.processes", "test") == []
