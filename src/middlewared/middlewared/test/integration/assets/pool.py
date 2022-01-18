import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, pool


@contextlib.contextmanager
def dataset(name):
    dataset = f"{pool}/{name}"

    call("pool.dataset.create", {"name": dataset})

    try:
        yield dataset
    finally:
        try:
            call("pool.dataset.delete", dataset, {"recursive": True})
        except InstanceNotFound:
            pass
