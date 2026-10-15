import pytest

from middlewared.plugins.pool_.sed import PoolService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test_update_all_sed_attr_judges_only_imported_pools():
    """An exported pool has no topology and must not be written to; an imported pool is."""
    m = Middleware()
    m["pool.query"] = m._query_filter(
        [
            {"id": 1, "name": "exported", "all_sed": True, "topology": None},
            {
                "id": 2,
                "name": "tank",
                "all_sed": None,
                "topology": {
                    "data": [
                        {"type": "DISK", "disk": "sda", "children": []},
                    ]
                },
            },
        ]
    )
    m["disk.query"] = lambda filters, options: [{"name": "sda", "sed_status": "UNLOCKED"}]
    m["pool.flatten_topology"] = lambda topology: [v for vdevs in topology.values() for v in vdevs]
    updates = []
    m["datastore.update"] = lambda table, pk, data: updates.append((pk, data))

    await PoolService(m).update_all_sed_attr(True)

    assert updates == [(2, {"vol_all_sed": True})]
