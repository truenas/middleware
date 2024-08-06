from time import sleep

import pytest

from middlewared.test.integration.assets.pool import _2_disk_mirror_topology, _4_disk_raidz2_topology, another_pool
from middlewared.test.integration.utils import call


@pytest.mark.parametrize("topology", [_2_disk_mirror_topology, _4_disk_raidz2_topology])
def test_pool_replace_disk(topology):
    """This tests the following:
        1. create a zpool based on the `topology`
        2. flatten the newly created zpools topology
        3. verify the zpool vdev size matches reality
        4. choose 1st vdev from newly created zpool
        5. choose 1st disk in vdev from step #4
        6. choose 1st disk in disk.get_unused as replacement disk
        7. call pool.replace using disk from step #5 with disk from step #6
        8. validate that the disk being replaced still has zfs partitions
        9. validate pool.get_instance topology info shows the replacement disk
        10. validate disk.get_instance associates the replacement disk with the zpool
    """
    with another_pool(topology=topology) as pool:  # step 1
        # step 2
        flat_top = call("pool.flatten_topology", pool["topology"])
        pool_top = [vdev for vdev in flat_top if vdev["type"] == "DISK"]
        # step 3
        assert len(pool_top) == topology[0]

        # step 4
        to_replace_vdev = pool_top[0]
        # step 5
        to_replace_disk = call(
            "disk.query", [["devname", "=", to_replace_vdev["disk"]]], {"get": True, "extra": {"pools": True}}
        )
        assert to_replace_disk["pool"] == pool["name"]

        # step 6
        new_disk = call("disk.get_unused")[0]

        # step 7
        call("pool.replace", pool["id"], {"label": to_replace_vdev["guid"], "disk": new_disk["identifier"]}, job=True)

        # step 8
        assert call("disk.gptid_from_part_type", to_replace_disk["devname"], call("disk.get_zfs_part_type"))

        # step 9
        found = False
        for _ in range(10):
            if not found:
                for i in call("pool.flatten_topology", call("pool.get_instance", pool["id"])["topology"]):
                    if i["type"] == "DISK" and i["disk"] == new_disk["devname"]:
                        found = True
                        break
                else:
                    sleep(1)

        assert found, f'Failed to detect replacement disk {new_disk["devname"]!r} in zpool {pool["name"]!r}'

        # step 10 (NOTE: disk.sync_all takes awhile so we retry a few times here)
        for _ in range(30):
            cmd = ("disk.get_instance", new_disk["identifier"], {"extra": {"pools": True}})
            if call(*cmd)["pool"] == pool["name"]:
                break
            else:
                sleep(1)
        else:
            assert False, f"{' '.join(cmd)} failed to update with pool information"
