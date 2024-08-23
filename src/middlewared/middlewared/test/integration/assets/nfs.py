# -*- coding=utf-8 -*-
import contextlib
import logging

from middlewared.test.integration.utils import call
from time import sleep

logger = logging.getLogger(__name__)

__all__ = ["nfs_share", "nfs_server"]


@contextlib.contextmanager
def nfs_server():
    try:
        res = call('service.start', 'nfs', {'silent': False})
        sleep(1)
        yield res
    finally:
        call('service.stop', 'nfs', {'silent': False})


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
