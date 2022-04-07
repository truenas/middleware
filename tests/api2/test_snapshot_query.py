import pytest

from middlewared.test.integration.assets.pool import dataset, pool, another_pool
from middlewared.test.integration.utils import call

from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


@pytest.fixture(scope="module")
def fixture1():
    with another_pool():
        with dataset("test"):
            with dataset("test/test1"):
                with dataset("test/test2"):
                    with dataset("test", pool="test"):
                        with dataset("test/test1", pool="test"):
                            with dataset("test/test2", pool="test"):
                                call(
                                    "zfs.snapshot.create",
                                    {"dataset": f"{pool}/test", "name": "snap-1", "recursive": True},
                                )
                                call(
                                    "zfs.snapshot.create",
                                    {"dataset": f"{pool}/test", "name": "snap-2", "recursive": True},
                                )
                                call(
                                    "zfs.snapshot.create",
                                    {"dataset": "test/test", "name": "snap-1", "recursive": True},
                                )
                                call(
                                    "zfs.snapshot.create",
                                    {"dataset": "test/test", "name": "snap-2", "recursive": True},
                                )
                                yield


def test_query_all_names(fixture1):
    names = {
        snapshot["name"]
        for snapshot in call("zfs.snapshot.query", [], {"select": ["name"]})
    }
    assert {f"{pool}/test@snap-1", f"{pool}/test@snap-2", f"{pool}/test/test1@snap-1", f"{pool}/test/test1@snap-2",
            f"{pool}/test/test2@snap-1", f"{pool}/test/test2@snap-2",
            f"test/test@snap-1", f"test/test@snap-2", f"test/test/test1@snap-1", f"test/test/test1@snap-2",
            f"test/test/test2@snap-1", f"test/test/test2@snap-2"}.issubset(names)


@pytest.mark.parametrize("filters,names", [
    ([["pool", "=", "test"]], {f"test/test@snap-1", f"test/test@snap-2", f"test/test/test1@snap-1",
                               f"test/test/test1@snap-2", f"test/test/test2@snap-1", f"test/test/test2@snap-2"}),
    ([["dataset", "=", f"{pool}/test"]], {f"{pool}/test@snap-1", f"{pool}/test@snap-2"}),
    ([["dataset", "in", [f"{pool}/test/test1", "test/test/test2"]]], {f"{pool}/test/test1@snap-1",
                                                                      f"{pool}/test/test1@snap-2",
                                                                      f"test/test/test2@snap-1",
                                                                      f"test/test/test2@snap-2"}),
])
def test_query_names_by_pool_or_dataset(fixture1, filters, names):
    assert {
        snapshot["name"]
        for snapshot in call("zfs.snapshot.query", filters, {"select": ["name"]})
    } == names
