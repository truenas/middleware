# -*- coding=utf-8 -*-
import ipaddress
import logging

logger = logging.getLogger(__name__)

__all__ = ["ipv6_netmask_to_prefixlen"]


def ipv6_netmask_to_prefixlen(netmask):
    bits = bin(ipaddress.IPv6Address._ip_int_from_string(netmask))[2:].rstrip("0")
    if not all(c == "1" for c in bits):
        raise ValueError("Invalid IPv6 netmask %r", netmask)

    return len(bits)
