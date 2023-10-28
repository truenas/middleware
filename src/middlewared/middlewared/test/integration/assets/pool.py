import contextlib
import time

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, pool


mirror_topology = (2, lambda disks: {
    "data": [
        {"type": "MIRROR", "disks": disks[0:2]}
    ],
})

another_pool_topologies = [
    (1, lambda disks: {
        "data": [
            {"type": "STRIPE", "disks": disks[0:1]},
        ],
    }),
    mirror_topology,
    (4, lambda disks: {
        "data": [
            {
                "type": "RAIDZ2",
                "disks": disks[0:4]
            }
        ],
    }),
]


@contextlib.contextmanager
def another_pool(data=None, topology=None):
    data = data or {}

    if topology is None:
        topology = another_pool_topologies[0]

    unused = call("disk.get_unused")
    if len(unused) < topology[0]:
        raise RuntimeError(f"At least {topology[0]} unused disks required to test this pool topology")

    pool = call("pool.create", {
        "name": "test",
        "encryption": False,
        "allow_duplicate_serials": True,
        "topology": topology[1]([d["devname"] for d in unused]),
        **data,
    }, job=True)

    try:
        yield pool
    finally:
        call("pool.export", pool["id"], job=True)


@contextlib.contextmanager
def dataset(name, data=None, pool=pool, **kwargs):
    data = data or {}

    dataset = f"{pool}/{name}"

    call("pool.dataset.create", {"name": dataset, **data})

    try:
        if "acl" in kwargs or "mode" in kwargs:
            if "acl" in kwargs:
                call("filesystem.setacl", {'path': f"/mnt/{dataset}", "dacl": kwargs['acl']})
            else:
                call("filesystem.setperm", {'path': f"/mnt/{dataset}", "mode": kwargs['mode'] or "777"})

        yield dataset
    finally:
        if 'delete_delay' in kwargs:
            time.sleep(kwargs['delete_delay'])

        try:
            call("pool.dataset.delete", dataset, {"recursive": True})
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def snapshot(dataset, name, **kwargs):
    get = kwargs.pop("get", False)

    result = call("zfs.snapshot.create", {"dataset": dataset, "name": name, **kwargs})

    id = f"{dataset}@{name}"
    try:
        if get:
            yield result
        else:
            yield id
    finally:
        try:
            call("zfs.snapshot.delete", id, {"recursive": True})
        except InstanceNotFound:
            pass
