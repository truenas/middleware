# -*- coding=utf-8 -*-
import contextlib
import logging

from middlewared.test.integration.utils import call

logger = logging.getLogger(__name__)

__all__ = ["smb_share"]


@contextlib.contextmanager
def smb_share(path, name, options=None):
    share = call("sharing.smb.create", {
        "path": path,
        "name": name,
        **(options or {})
    })
    assert call("service.start", "cifs")

    try:
        yield share
    finally:
        call("sharing.smb.delete", share["id"])
        call("service.stop", "cifs")
