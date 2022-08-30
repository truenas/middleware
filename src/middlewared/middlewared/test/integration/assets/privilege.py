import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def privilege(data):
    privilege = call("privilege.create", data)

    try:
        yield privilege
    finally:
        try:
            call("privilege.delete", privilege["id"])
        except InstanceNotFound:
            pass
