import pytest

from middlewared.test.integration.assets.pool import test_pool_topologies, test_pool
from middlewared.test.integration.utils import call


def disks(topology):
    flat = call("pool.flatten_topology", topology)
    return [vdev for vdev in flat if vdev["type"] == "DISK"]


@pytest.mark.parametrize("topology", test_pool_topologies[1:])
@pytest.mark.parametrize("i", list(range(0, max(topology[0] for topology in test_pool_topologies))))
@pytest.mark.skip(reason="Global crisis, 8 GB virtual HDDs are temporary out of stock")
def test_pool_replace_disk(topology, i):
    count = topology[0]
    if i >= count:
        return

    with test_pool(topology=topology) as pool:
        assert len(disks(pool["topology"])) == count

        to_replace_vdev = disks(pool["topology"])[i]
        to_replace_disk = call("disk.query", [["devname", "=", to_replace_vdev["disk"]]],
                               {"get": True, "extra": {"pools": True}})
        assert to_replace_disk["pool"] == pool["name"]

        new_disk = call("disk.get_unused")[0]

        call("pool.replace", pool["id"], {
            "label": to_replace_vdev["guid"],
            "disk": new_disk["identifier"],
            "force": True,
        }, job=True)

        pool = call("pool.get_instance", pool["id"])

        assert len(disks(pool["topology"])) == count
        assert disks(pool["topology"])[i]["disk"] == new_disk["devname"]

        assert call("disk.get_instance", new_disk["identifier"], {"extra": {"pools": True}})["pool"] == pool["name"]
        assert call("disk.get_instance", to_replace_disk["identifier"], {"extra": {"pools": True}})["pool"] is None
