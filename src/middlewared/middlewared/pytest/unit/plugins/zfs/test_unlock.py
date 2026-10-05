import pytest

from middlewared.plugins.zfs.encryption_lock import assign_supplied_recursive_keys


@pytest.mark.parametrize(
    "request_datasets,keys_supplied,queried_datasets,result",
    [
        (
            [
                {"path": "tank/test", "recursive": True},
                {"path": "tank/test/child", "recursive": True},
                {"path": "tank/test/child/grandchild", "recursive": False},
            ],
            {"tank/test": "test-key", "tank/test/child": "child-key", "tank/test/child/grandchild": "grandchild-key"},
            [
                "tank/test",
                "tank/test/another-child",
                "tank/test/child",
                "tank/test/child/grandchild",
                "tank/test/child/grandchild/grandgrandchild",
            ],
            {
                "tank/test": "test-key",
                "tank/test/another-child": "test-key",
                "tank/test/child": "child-key",
                "tank/test/child/grandchild": "grandchild-key",
                "tank/test/child/grandchild/grandgrandchild": "child-key",
            },
        )
    ],
)
def test_assign_supplied_recursive_keys(request_datasets, keys_supplied, queried_datasets, result):
    assign_supplied_recursive_keys(request_datasets, keys_supplied, queried_datasets)
    assert keys_supplied == result
