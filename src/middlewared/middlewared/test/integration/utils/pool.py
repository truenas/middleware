# -*- coding=utf-8 -*-
import logging
import os
import sys

from .ssh import ssh

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import pool_name
except ImportError:
    pool_name = os.environ.get("ZPOOL")

logger = logging.getLogger(__name__)

__all__ = ["fault_vdev", "pool"]

pool = pool_name


def fault_vdev(pool_name, vdev):
    # ZFS degrades instead of faults a vdev that holds the only copy of the data
    ssh(f"zinject -d {vdev} -A fault {pool_name}")
