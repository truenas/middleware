import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, pool


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
