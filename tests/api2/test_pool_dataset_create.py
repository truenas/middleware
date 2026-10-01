from itertools import product
from re import escape
import shlex

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh


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


@pytest.fixture(scope="module")
def space_names():
    with dataset("space_names") as ds:
        yield ds


@pytest.mark.parametrize(
    "name,create_ancestors,new_ancestor",
    [
        pytest.param("trail ", False, None, id="trailing space"),
        pytest.param(" leading", False, None, id="leading space"),
        pytest.param("mid /trail", True, "mid ", id="trailing space in a created ancestor"),
        pytest.param(" mid/leading", True, " mid", id="leading space in a created ancestor"),
    ],
)
def test_pool_dataset_create_space_padded_name(space_names, name, create_ancestors, new_ancestor):
    if new_ancestor:
        error = f"Cannot create '{space_names}/{new_ancestor}': dataset names may not begin or end with a space"
    else:
        error = "Dataset names may not begin or end with a space"
    with pytest.raises(ValidationErrors, match=escape(error)):
        call("pool.dataset.create", {"name": f"{space_names}/{name}", "create_ancestors": create_ancestors})


def test_pool_dataset_create_allowed_spaces(space_names):
    ds = space_names
    call("pool.dataset.create", {"name": f"{ds}/my dataset/child", "create_ancestors": True})

    # an existing padded name, as on older pools, still takes children and can be renamed clean
    ssh(f"zfs create {shlex.quote(f'{ds}/legacy ')}")
    call("pool.dataset.create", {"name": f"{ds}/legacy /child", "create_ancestors": True})
    call("pool.dataset.rename", f"{ds}/legacy ", {"new_name": f"{ds}/legacy", "force": True})

    with pytest.raises(ValidationErrors, match="Dataset names may not begin or end with a space"):
        call("pool.dataset.rename", f"{ds}/legacy", {"new_name": f"{ds}/ legacy", "force": True})


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
