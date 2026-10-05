import contextlib

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call

__all__ = ["webshare_share"]


@contextlib.contextmanager
def webshare_share(path, name, options=None):
    share = call("sharing.webshare.create", {"path": path, "name": name, **(options or {})})

    try:
        yield share
    finally:
        with contextlib.suppress(InstanceNotFound):
            call("sharing.webshare.delete", share["id"])
