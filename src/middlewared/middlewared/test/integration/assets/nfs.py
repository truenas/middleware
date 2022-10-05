# -*- coding=utf-8 -*-
import contextlib
import logging

from middlewared.test.integration.utils import call

logger = logging.getLogger(__name__)

__all__ = ["nfs_share"]


@contextlib.contextmanager
def nfs_share(dataset):
    share = call("sharing.nfs.create", {
        "path": f"/mnt/{dataset}",
    })
    assert call("service.start", "nfs")

    try:
        yield share
    finally:
        call("sharing.nfs.delete", share["id"])
        call("service.stop", "nfs")
