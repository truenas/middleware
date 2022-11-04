import pytest

from time import sleep
from middlewared.test.integration.assets.pool import mirror_topology, another_pool_topologies, another_pool
from middlewared.test.integration.utils import call

from auto_config import dev_test, ha
pytestmark = [
    pytest.mark.skipif(dev_test, reason='Skipping for test development testing'),
    pytest.mark.skipif(ha, reason='Skipping for HA testing'),
]


def disks(topology):
    flat = call("pool.flatten_topology", topology)
    return [vdev for vdev in flat if vdev["type"] == "DISK"]


@pytest.mark.parametrize("topology", another_pool_topologies[1:])
@pytest.mark.parametrize("i", list(range(0, max(topology[0] for topology in another_pool_topologies))))
def test_pool_replace_disk(topology, i):
    count = topology[0]
    if i >= count:
        return

    with another_pool(topology=topology) as pool:
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

        # Sometimes the VM is slow so look 5 times with 1 second in between
        for _ in range(5):
            pool = call("pool.get_instance", pool["id"])
            if len(disks(pool["topology"])) == count:
                break
            sleep(1)

        assert len(disks(pool["topology"])) == count
        assert disks(pool["topology"])[i]["disk"] == new_disk["devname"]

        assert call("disk.get_instance", new_disk["identifier"], {"extra": {"pools": True}})["pool"] == pool["name"]
        assert call("disk.get_instance", to_replace_disk["identifier"], {"extra": {"pools": True}})["pool"] is None


def test_pool_replace_disk_with_larger_swap():
    unused = call("disk.get_unused")
    if len(unused) < 3:
        raise RuntimeError(f"At least 3 unused disks required to run this test")

    test_disks = unused[:3]

    sizes = {disk["name"]: disk["size"] for disk in test_disks}
    assert len(set(sizes.values())) == 1, sizes

    with another_pool(topology=mirror_topology) as pool:
        to_replace_vdev = disks(pool["topology"])[0]

        call("system.advanced.update", {"swapondrive": 4})
        try:
            call("pool.replace", pool["id"], {
                "label": to_replace_vdev["guid"],
                "disk": test_disks[2]["identifier"],
                "force": True,
            }, job=True)
        finally:
            call("system.advanced.update", {"swapondrive": 2})
