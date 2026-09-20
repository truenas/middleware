import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call

from auto_config import pool_name


def test_prefetch_single_pool():
    call("zfs.resource.pool.prefetch", pool_name)


def test_prefetch_nonexistent_pool_raises():
    with pytest.raises(CallError) as ce:
        call("zfs.resource.pool.prefetch", "test_prefetch_no_such_pool")
    assert "test_prefetch_no_such_pool" in str(ce.value)


def test_prefetch_pools_skips_boot_pool():
    boot_pool = call("boot.pool_name")
    call("zfs.resource.pool.prefetch_pools")

    logged = call("zfs.resource.list", {"paths": [boot_pool], "properties": None})
    assert logged, "the boot pool must still be queryable after prefetch_pools"


def test_prefetch_runs_after_a_pool_is_imported():
    """pool.post_import prefetches the metadata of the pool that came back"""
    with another_pool({"name": "test_prefetch_pool"}) as pool:
        call("zfs.resource.create", {"path": f"{pool['name']}/ds"})
        call("pool.export", pool["id"], job=True)
        call("pool.import_pool", {"guid": pool["guid"], "name": pool["name"]}, job=True)

        result = call(
            "zfs.resource.list",
            {"paths": [pool["name"]], "get_children": True, "properties": None},
        )
        assert f"{pool['name']}/ds" in [r["name"] for r in result]
