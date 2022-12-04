from unittest.mock import Mock

import pytest

from middlewared.plugins.pool_.dataset_encryption_lock import PoolDatasetService


@pytest.mark.parametrize("request_datasets,keys_supplied,queried_datasets,result", [
    (
        [{"name": "tank/test", "recursive": True}, {"name": "tank/test/child", "recursive": True},
         {"name": "tank/test/child/grandchild", "recursive": False}],
        {"tank/test": "test-key", "tank/test/child": "child-key", "tank/test/child/grandchild": "grandchild-key"},
        ["tank/test", "tank/test/another-child", "tank/test/child", "tank/test/child/grandchild",
         "tank/test/child/grandchild/grandgrandchild"],
        {
            "tank/test": "test-key",
            "tank/test/another-child": "test-key",
            "tank/test/child": "child-key",
            "tank/test/child/grandchild": "grandchild-key",
            "tank/test/child/grandchild/grandgrandchild": "child-key",
        }
    )
])
def test_assign_supplied_recursive_keys(request_datasets, keys_supplied, queried_datasets, result):
    PoolDatasetService(Mock())._assign_supplied_recursive_keys(request_datasets, keys_supplied, queried_datasets)
    assert keys_supplied == result
