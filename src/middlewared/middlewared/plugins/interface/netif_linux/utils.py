# -*- coding=utf-8 -*-
import logging
import subprocess

logger = logging.getLogger(__name__)

__all__ = ["bitmask_to_set", "INTERNAL_INTERFACES", "run"]


INTERNAL_INTERFACES = [
    "wg", "lo", "tun", "tap", "docker", "veth", "kube-bridge", "kube-dummy-if", "vnet", "openvpn", "macvtap",
]


def bitmask_to_set(n, enumeration):
    return {e for e in enumeration if n & e.value}


def run(*args, **kwargs):
    kwargs.setdefault("check", True)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.PIPE)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "ignore")
    return subprocess.run(*args, **kwargs)
