import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def vmware(data):
    vmware = call("vmware.create", data)

    try:
        yield vmware
    finally:
        call("vmware.delete", vmware["id"])
