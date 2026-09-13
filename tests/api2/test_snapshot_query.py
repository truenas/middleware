import pytest

from middlewared.test.integration.assets.pool import dataset, pool, another_pool
from middlewared.test.integration.utils import call



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
                                    "pool.snapshot.create",
                                    {"dataset": f"{pool}/test", "name": "snap-1", "recursive": True},
                                )
                                call(
                                    "pool.snapshot.create",
                                    {"dataset": f"{pool}/test", "name": "snap-2", "recursive": True},
                                )
                                call(
                                    "pool.snapshot.create",
                                    {"dataset": "test/test", "name": "snap-1", "recursive": True},
                                )
                                call(
                                    "pool.snapshot.create",
                                    {"dataset": "test/test", "name": "snap-2", "recursive": True},
                                )
                                yield


def test_query_all_names(fixture1):
    names = {
        snapshot["name"]
        for snapshot in call("pool.snapshot.query", [], {"select": ["name"]})
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
        for snapshot in call("pool.snapshot.query", filters, {"select": ["name"]})
    } == names


def test_extra_properties_returns_user_properties():
    """A name containing a colon is a user property and is read as one."""
    with dataset("test_snap_query_user_props") as ds:
        call("pool.snapshot.create", {
            "dataset": ds, "name": "snap",
            "properties": {"com.example:one": "1", "com.example:two": "2"},
        })

        snap = call("pool.snapshot.query", [["dataset", "=", ds]], {
            "extra": {"properties": ["creation", "com.example:one", "com.example:two"]},
        })[0]

        assert snap["properties"]["com.example:one"]["value"] == "1"
        assert snap["properties"]["com.example:one"]["source"] == "LOCAL"
        assert snap["properties"]["com.example:two"]["value"] == "2"
        assert snap["properties"]["creation"]["source"] == "NONE"


def test_extra_properties_omits_user_properties_that_are_not_set():
    with dataset("test_snap_query_unset_user_prop") as ds:
        call("pool.snapshot.create", {"dataset": ds, "name": "snap"})

        snap = call("pool.snapshot.query", [["dataset", "=", ds]], {
            "extra": {"properties": ["com.example:nope"]},
        })[0]

        assert snap["properties"] == {}


def test_extra_properties_user_properties_alongside_retention_and_holds():
    with dataset("test_snap_query_user_props_extra") as ds:
        call("pool.snapshot.create", {
            "dataset": ds, "name": "snap", "properties": {"com.example:one": "1"},
        })

        snap = call("pool.snapshot.query", [["dataset", "=", ds]], {
            "extra": {"retention": True, "holds": True, "properties": ["com.example:one"]},
        })[0]

        assert snap["properties"]["com.example:one"]["value"] == "1"
        assert "holds" in snap
        assert "retention" in snap
