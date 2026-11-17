from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import client, fault_vdev, poll

# A mirror, so that ZFS faults the disk instead of degrading it
MIRROR = (2, lambda disks: {"data": [{"type": "MIRROR", "disks": disks[0:2]}]})


def disk_status(pool, guid):
    return next(
        (disk["status"] for vdev in pool["topology"]["data"] for disk in vdev["children"] if disk["guid"] == guid),
        None,
    )


def test_faulted_disk_sends_pool_query_changed():
    with another_pool(topology=MIRROR) as pool:
        guid = pool["topology"]["data"][0]["children"][0]["guid"]
        statuses = []

        with client() as c:

            def callback(type, **message):
                if type == "CHANGED" and message["id"] == pool["id"]:
                    statuses.append(disk_status(message["fields"], guid))

            c.subscribe("pool.query", callback, sync=True)

            fault_vdev(pool["name"], guid)

            poll(
                lambda: statuses,
                condition=lambda received: "FAULTED" in received,
                timeout=60,
                message=f"No pool.query CHANGED event showed disk {guid} as FAULTED",
            )
