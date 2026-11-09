import contextlib
import errno

from truenas_api_client import ValidationErrors

from middlewared.plugins.zfs.exceptions import ZFSPathNotFoundException
from middlewared.service_exception import CallError, InstanceNotFound, MatchNotFound
from middlewared.test.integration.utils import call, fail, pool, ssh
from middlewared.test.integration.utils.disk import retry_get_parts_on_disk

_1_disk_stripe_topology = (1, lambda disks: {
    "data": [{"type": "STRIPE", "disks": disks[0:1]}],
})
_2_disk_mirror_topology = (2, lambda disks: {
    "data": [{"type": "MIRROR", "disks": disks[0:2]}],
})
_4_disk_raidz2_topology = (4, lambda disks: {
    "data": [{"type": "RAIDZ2", "disks": disks[0:4]}],
})
another_pool_topologies = [
    _1_disk_stripe_topology,
    _2_disk_mirror_topology,
    _4_disk_raidz2_topology,
]


@contextlib.contextmanager
def another_pool(data=None, topology=None):
    data = data or {}

    if topology is None:
        topology = another_pool_topologies[0]

    unused = call("disk.get_unused")
    if len(unused) < topology[0]:
        raise RuntimeError(f"At least {topology[0]} unused disks required to test this pool topology")

    try:
        pool = call("pool.create", {
            "name": "test",
            "encryption": False,
            "allow_duplicate_serials": True,
            "topology": topology[1]([d["devname"] for d in unused]),
            **data,
        }, job=True)
    except ValidationErrors as e:
        if any(error.attribute == "pool_create.name" and error.errcode == errno.EEXIST for error in e.errors):
            fail("Previous `another_pool` fixture failed to teardown. Aborting tests.")

        raise

    try:
        yield pool
    finally:
        pool_id = pool["id"]
        # If the pool has been exported and reimported then it may change id
        # Therefore query by the guid to see if this is the case.
        try:
            pool_id = call('pool.query', [['guid', '=', pool['guid']]], {'get': True})['id']
        except MatchNotFound:
            pass
        try:
            call("pool.export", pool_id, {"destroy": True}, job=True)
        except ValidationErrors as e:
            if not any(error.errcode == errno.ENOENT for error in e.errors):
                raise
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def dataset(name, data=None, pool=pool, **kwargs):
    data = data or {}

    dataset = f"{pool}/{name}"

    call("pool.dataset.create", {"name": dataset, **data})

    try:
        if "acl" in kwargs:
            call("filesystem.setacl", {'path': f"/mnt/{dataset}", "dacl": kwargs['acl']})
        elif "mode" in kwargs:
            call("filesystem.setperm", {'path': f"/mnt/{dataset}", "mode": kwargs['mode'] or "777"})

        yield dataset
    finally:
        if kwargs.get('delete', True):
            try:
                call("pool.dataset.delete", dataset, {"recursive": True})
            except InstanceNotFound:
                pass
            except CallError as e:
                if "dataset already exists" in str(e):
                    call("pool.dataset.delete", dataset, {"recursive": True})
                else:
                    raise


@contextlib.contextmanager
def snapshot(dataset, name, **kwargs):
    get = kwargs.pop("get", False)

    result = call(
        "zfs.resource.snapshot.create",
        {"dataset": dataset, "name": name, **kwargs}
    )
    id_ = f"{dataset}@{name}"
    try:
        if get:
            yield result
        else:
            yield id_
    finally:
        try:
            call("zfs.resource.snapshot.destroy", {"path": id_, "recursive": True})
        except ZFSPathNotFoundException:
            pass


@contextlib.contextmanager
def resized_partitions_pool(topology, partition_size_delta):
    # Older releases created data partitions of other sizes, e.g. without the reserve at the end of the disk
    with another_pool(topology=topology) as pool:
        vdevs = [vdev for vdev in call("pool.flatten_topology", pool["topology"]) if vdev["type"] == "DISK"]

        assert len(vdevs) == topology[0]

        default_partitions_sizes = {
            retry_get_parts_on_disk(vdev["disk"])[-1]["size"]
            for vdev in vdevs
        }
        assert len(default_partitions_sizes) == 1
        default_partition_size = default_partitions_sizes.pop()

        size_k = int((default_partition_size + partition_size_delta) / 1024.0)
        ssh(f"zpool export {pool['name']}")
        devices = []
        for vdev in vdevs:
            ssh(f"sgdisk -d 1 /dev/{vdev['disk']}")
            ssh(f"sgdisk -n 1:0:+{size_k}k -t 1:BF01 /dev/{vdev['disk']}")
            partition = retry_get_parts_on_disk(vdev["disk"])[-1]
            assert partition["size"] == size_k * 1024
            devices.append("disk/by-partuuid/" + partition["partition_uuid"])

        vdev_type = pool["topology"]["data"][0]["type"].lower()
        if vdev_type == "disk":
            vdev_type = ""

        ssh(f"zpool create {pool['name']} -o altroot=/mnt -f {vdev_type} {' '.join(devices)}")
        pool = call("pool.get_instance", pool["id"])
        yield pool



@contextlib.contextmanager
def oversize_pool():
    with resized_partitions_pool(_2_disk_mirror_topology, 10 * 1024 * 1024) as pool:
        yield pool


@contextlib.contextmanager
def draid_pool():
    unused_disks = call("disk.get_unused")
    assert len(unused_disks) >= 2

    with another_pool(
        {
            "name": "test_draid_pool",
            "topology": {
                "data": [
                    {
                        "disks": [disk["name"] for disk in unused_disks[:2]],
                        "type": "DRAID1",
                        "draid_data_disks": 1,
                    }
                ],
            },
            "allow_duplicate_serials": True,
        }
    ) as pool:
        yield pool
