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
        res = call('service.control', 'START', 'nfs', {'silent': False}, job=True)
        sleep(1)
        yield res
    finally:
        call('service.control', 'STOP', 'nfs', {'silent': False}, job=True)


@contextlib.contextmanager
def nfs_share(dataset):
    share = call("sharing.nfs.create", {
        "path": f"/mnt/{dataset}",
    })
    assert call("service.control", "START", "nfs", job=True)

    try:
        yield share
    finally:
        call("sharing.nfs.delete", share["id"])
        call("service.control", "STOP", "nfs", job=True)
