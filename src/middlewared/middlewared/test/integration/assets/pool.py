import contextlib
import errno
import time

from truenas_api_client import ValidationErrors

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, fail, pool

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
        try:
            call("pool.export", pool["id"], {"destroy": True}, job=True)
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

    id_ = f"{dataset}@{name}"
    try:
        if get:
            yield result
        else:
            yield id_
    finally:
        try:
            call("zfs.snapshot.delete", id_, {"recursive": True})
        except InstanceNotFound:
            pass
