import contextlib

from middlewared.test.integration.utils import call, pool


@contextlib.contextmanager
def dataset(name):
    assert "/" not in name

    dataset = f"{pool}/{name}"

    call("pool.dataset.create", {"name": dataset})

    try:
        yield dataset
    finally:
        call("pool.dataset.delete", dataset)
