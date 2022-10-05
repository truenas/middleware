import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def snapshot_task(data):
    task = call("pool.snapshottask.create", data)

    try:
        yield task
    finally:
        call("pool.snapshottask.delete", task["id"])
