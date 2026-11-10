import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.disk import fake_disks
from middlewared.test.integration.assets.pool import (
    _1_disk_stripe_topology, another_pool, oversize_pool, resized_partitions_pool,
)
from middlewared.test.integration.utils import call, fault_vdev, poll
from middlewared.test.integration.utils.disk import retry_get_parts_on_disk


def data_partition_size(disk):
    return retry_get_parts_on_disk(disk)[-1]["size"]


def resilvered_spare_disks(pool_id):
    pool = call("pool.get_instance", pool_id)
    if pool["scan"] is None or (pool["scan"]["function"], pool["scan"]["state"]) != ("RESILVER", "FINISHED"):
        return set()

    return {
        child["disk"]
        for vdev in call("pool.flatten_topology", {"data": pool["topology"]["data"]})
        if vdev["type"] == "SPARE"
        for child in vdev["children"]
        if child["status"] == "ONLINE"
    }


def fault_disk_and_wait_for_spare(pool, disk, spare):
    member = next(
        vdev for vdev in call("pool.flatten_topology", call("pool.get_instance", pool["id"])["topology"])
        if vdev["type"] == "DISK" and vdev["disk"] == disk
    )
    # ZED activates the spare, as it does when a real disk fails
    fault_vdev(pool["name"], member["guid"])

    poll(
        lambda: resilvered_spare_disks(pool["id"]),
        condition=lambda disks: spare in disks,
        timeout=60,
        message=f"Spare {spare} did not replace faulted disk {disk}",
    )


def test_pool_create_too_small_spare():
    disk = call("disk.get_unused")[0]["name"]

    with fake_disks({"sdz": {"size_bytes": 1024 * 1024 * 1024}}):
        with pytest.raises(ValidationErrors) as ve:
            pool = call("pool.create", {
                "name": "test",
                "encryption": False,
                "allow_duplicate_serials": True,
                "topology": {
                    "data": [
                        {"type": "STRIPE", "disks": [disk]},
                    ],
                    "spares": ["sdz"],
                },
            }, job=True)
            call("pool.export", pool["id"], job=True)

        assert ve.value.errors[0].errmsg.startswith("Spare sdz (1 GiB) is smaller than the smallest data disk")


def test_pool_update_spare():
    with another_pool() as pool:
        # Test too small
        with fake_disks({"sdz": {"size_bytes": 1024 * 1024 * 1024}}):
            with pytest.raises(ValidationErrors) as ve:
                call("pool.update", pool["id"], {
                    "topology": {
                        "spares": ["sdz"],
                    },
                }, job=True)

            assert ve.value.errors[0].errmsg.startswith("Spare sdz (1 GiB) is smaller than the smallest data disk")

        # Test multiple spares
        spares = [disk["name"] for disk in call("disk.get_unused")[:2]]
        assert len(spares) == 2

        result = call("pool.update", pool["id"], {"topology": {"spares": spares}}, job=True)
        assert {disk["disk"] for disk in result["topology"]["spare"]} == set(spares)


def test_pool_update_spare_matches_oversize_data_partitions():
    with oversize_pool() as pool:
        data_disks = [
            vdev["disk"] for vdev in call("pool.flatten_topology", pool["topology"]) if vdev["type"] == "DISK"
        ]
        spare = call("disk.get_unused")[0]["name"]

        call("pool.update", pool["id"], {"topology": {"spares": [spare]}}, job=True)

        assert data_partition_size(spare) == min(data_partition_size(disk) for disk in data_disks)

        fault_disk_and_wait_for_spare(pool, data_disks[0], spare)


def test_pool_update_spare_matches_new_data_vdev():
    with resized_partitions_pool(_1_disk_stripe_topology, -10 * 1024 * 1024) as pool:
        data_disk, spare = [disk["name"] for disk in call("disk.get_unused")[:2]]

        call("pool.update", pool["id"], {
            "topology": {
                "data": [{"type": "STRIPE", "disks": [data_disk]}],
                "spares": [spare],
            },
        }, job=True)

        assert data_partition_size(spare) == data_partition_size(data_disk)

        fault_disk_and_wait_for_spare(pool, data_disk, spare)
