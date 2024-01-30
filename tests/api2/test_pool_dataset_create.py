import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

pytestmark = pytest.mark.zfs


@pytest.mark.parametrize("child", ["a/b", "a/b/c"])
def test_pool_dataset_create_ancestors(child):
    with dataset("ancestors_create_test") as test_ds:
        name = f"{test_ds}/{child}"
        call("pool.dataset.create", {"name": name, "create_ancestors": True})
        call("pool.dataset.get_instance", name)
