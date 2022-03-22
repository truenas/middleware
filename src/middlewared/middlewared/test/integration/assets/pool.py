import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, pool


@contextlib.contextmanager
def test_pool():
    unused = call("disk.get_unused")
    if not unused:
        raise RuntimeError("There are no unused disks")

    pool = call("pool.create", {
        "name": "test",
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": [unused[0]["devname"]]},
            ],
        }
    }, job=True)

    try:
        yield pool
    finally:
        call("pool.export", pool["id"], job=True)


@contextlib.contextmanager
def dataset(name, data=None):
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
