import errno

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call


def snapshot_exists(id_):
    return call("pool.snapshot.query", [["id", "=", id_]], {"count": True}) == 1


def test_pool_snapshot_rename():
    with dataset("test_pool_snap_rename") as ds:
        with snapshot(ds, "old_name") as snap:
            call(
                "pool.snapshot.rename",
                snap,
                {"new_name": f"{ds}@new_name", "force": True},
            )

            try:
                assert not snapshot_exists(snap)
                renamed = call(
                    "pool.snapshot.query",
                    [["id", "=", f"{ds}@new_name"]],
                    {"get": True},
                )
                assert renamed["snapshot_name"] == "new_name"
                assert renamed["dataset"] == ds
            finally:
                # Restore the original name so the fixture teardown finds the snapshot, otherwise
                # an assertion failure above is reported alongside a teardown error for it.
                call(
                    "pool.snapshot.rename",
                    f"{ds}@new_name",
                    {"new_name": snap, "force": True},
                )


def test_pool_snapshot_rename_requires_force():
    with dataset("test_pool_snap_rename_force") as ds:
        with snapshot(ds, "snap") as snap:
            with pytest.raises(ValidationError) as ve:
                call("pool.snapshot.rename", snap, {"new_name": f"{ds}@renamed"})

            assert ve.value.attribute == "pool.snapshot.rename.force"
            assert snapshot_exists(snap)


def test_pool_snapshot_rename_different_dataset():
    with dataset("test_pool_snap_rename_src") as src:
        with dataset("test_pool_snap_rename_dst") as dst:
            with snapshot(src, "snap") as snap:
                with pytest.raises(ValidationError) as ve:
                    call(
                        "pool.snapshot.rename",
                        snap,
                        {"new_name": f"{dst}@snap", "force": True},
                    )

                assert ve.value.attribute == "pool.snapshot.rename.new_name"
                assert snapshot_exists(snap)


def test_pool_snapshot_rename_nonexistent():
    with dataset("test_pool_snap_rename_noent") as ds:
        with pytest.raises(ValidationError) as ve:
            call(
                "pool.snapshot.rename",
                f"{ds}@nonexistent",
                {"new_name": f"{ds}@renamed", "force": True},
            )

        assert ve.value.errno == errno.ENOENT
