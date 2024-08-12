from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


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
