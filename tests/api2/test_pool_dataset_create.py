from itertools import product
from re import escape

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool


def test_create_dataset_nonexistent_pool():
    bad = "does_not_exist_zpool"
    with pytest.raises(
        ValidationErrors,
        match=escape(f"[EINVAL] pool_dataset_create.name: zpool ({bad}) does not exist.\n")
    ):
        with dataset("zz", pool=bad):
            pass


def test_create_dataset_nonexistent_parent_ds():
    bad = "zz"
    with pytest.raises(
        ValidationErrors,
        match=escape(f"[EINVAL] pool_dataset_create.name: Parent dataset ({pool}/{bad}) does not exist.\n")
    ):
        with dataset(f"{bad}/bleh"):
            pass


@pytest.mark.parametrize("child", ["a/b", "a/b/c"])
def test_pool_dataset_create_ancestors(child):
    with dataset("ancestors_create_test") as test_ds:
        name = f"{test_ds}/{child}"
        call("pool.dataset.create", {"name": name, "create_ancestors": True})
        call("pool.dataset.get_instance", name)


def test_pool_dataset_query():
    fields = ("id", "name")
    ops = ("=", "in")
    flats = (True, False)

    with dataset("query_test") as ds:
        # Try all combinations
        results = (call(
            "pool.dataset.query",
            [[field, op, ds if op == "=" else [ds]]],
            {"extra": {"flat": flat, "properties": []}}
        ) for field, op, flat in product(fields, ops, flats))

        # Check all the returns are the same
        first = next(results)
        for next_ds in results:
            assert next_ds == first
