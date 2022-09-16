import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, pool


another_pool_topologies = [
    (1, lambda disks: {
        "data": [
            {"type": "STRIPE", "disks": disks[0:1]},
        ],
    }),
    (2, lambda disks: {
        "data": [
            {"type": "MIRROR", "disks": disks[0:2]}
        ],
    }),
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
def dataset(name, data=None, pool=pool):
    data = data or {}

    dataset = f"{pool}/{name}"

    call("pool.dataset.create", {"name": dataset, **data})

    try:
        yield dataset
    finally:
        try:
            call("pool.dataset.delete", dataset, {"recursive": True})
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def snapshot(dataset, name, **kwargs):
    call("zfs.snapshot.create", {"dataset": dataset, "name": name, **kwargs})

    id = f"{dataset}@{name}"
    try:
        yield id
    finally:
        try:
            call("zfs.snapshot.delete", id)
        except InstanceNotFound:
            pass
