from middlewared.test.integration.assets.pool import another_pool, oversize_pool
from middlewared.test.integration.utils import call


def test_attach_stripe():
    with another_pool() as pool:
        disk = call("disk.get_unused")[0]["name"]

        call("pool.attach", pool["id"], {
            "target_vdev": pool["topology"]["data"][0]["guid"],
            "new_disk": disk,
        }, job=True)

        pool = call("pool.get_instance", pool["id"])
        assert pool["topology"]["data"][0]["type"] == "MIRROR"


def test_attach_raidz1_vdev():
    with another_pool(topology=(6, lambda disks: {
        "data": [
            {
                "type": "RAIDZ1",
                "disks": disks[0:3]
            },
            {
                "type": "RAIDZ1",
                "disks": disks[3:6]
            },
        ],
    })) as pool:
        disk = call("disk.get_unused")[0]["name"]

        call("pool.attach", pool["id"], {
            "target_vdev": pool["topology"]["data"][0]["guid"],
            "new_disk": disk,
        }, job=True)

        pool = call("pool.get_instance", pool["id"])
        assert pool["expand"]["state"] == "FINISHED"


def test_attach_oversize_pool():
    with oversize_pool() as pool:
        disk = call("disk.get_unused")[0]["name"]

        call("pool.attach", pool["id"], {
            "target_vdev": pool["topology"]["data"][0]["guid"],
            "new_disk": disk,
        }, job=True)
