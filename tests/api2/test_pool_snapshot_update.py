import pytest

from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


def user_properties(snap):
    return call(
        "zfs.resource.snapshot.query",
        {"paths": [snap], "get_user_properties": True},
    )[0]["user_properties"]


def test_pool_snapshot_update_sets_user_properties():
    with dataset("test_snap_update_set") as ds:
        with snapshot(ds, "snap") as snap:
            entry = call("pool.snapshot.update", snap, {
                "user_properties_update": [
                    {"key": "com.example:one", "value": "1"},
                    {"key": "com.example:two", "value": "2"},
                ],
            })

            assert entry["id"] == snap
            assert entry["properties"]["createtxg"]["value"]
            assert user_properties(snap) == {
                "com.example:one": "1",
                "com.example:two": "2",
            }


def test_pool_snapshot_update_removes_user_properties():
    with dataset("test_snap_update_remove") as ds:
        with snapshot(ds, "snap") as snap:
            call("pool.snapshot.update", snap, {
                "user_properties_update": [
                    {"key": "com.example:keep", "value": "yes"},
                    {"key": "com.example:drop", "value": "no"},
                ],
            })

            call("pool.snapshot.update", snap, {
                "user_properties_remove": ["com.example:drop"],
            })

            assert user_properties(snap) == {"com.example:keep": "yes"}


def test_pool_snapshot_update_remove_wins_over_update():
    with dataset("test_snap_update_conflict") as ds:
        with snapshot(ds, "snap") as snap:
            call("pool.snapshot.update", snap, {
                "user_properties_update": [{"key": "com.example:x", "value": "v"}],
                "user_properties_remove": ["com.example:x"],
            })

            assert user_properties(snap) == {}


def test_pool_snapshot_update_rejects_dataset_path():
    """A path without '@' must not fall through and update the dataset itself."""
    with dataset("test_snap_update_dataset_path") as ds:
        with pytest.raises(Exception) as exc_info:
            call("pool.snapshot.update", ds, {
                "user_properties_update": [{"key": "com.example:x", "value": "v"}],
            })
        assert "must be a snapshot path" in str(exc_info.value).lower()

        assert call(
            "zfs.resource.query",
            {"paths": [ds], "get_user_properties": True},
        )[0]["user_properties"] == {}


def test_pool_snapshot_update_nonexistent_snapshot():
    with dataset("test_snap_update_missing") as ds:
        with pytest.raises(Exception) as exc_info:
            call("pool.snapshot.update", f"{ds}@nope", {
                "user_properties_update": [{"key": "com.example:x", "value": "v"}],
            })
        assert "not found" in str(exc_info.value).lower()
