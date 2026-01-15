import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def snapshot_task(data):
    task = call("pool.snapshottask.create", data)

    try:
        yield task
    finally:
        try:
            call("pool.snapshottask.delete", task["id"])
        except InstanceNotFound:
            pass
