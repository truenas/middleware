# -*- coding=utf-8 -*-
import collections
import enum
import ipaddress
import logging
import os
import socket

import bidict
from pyroute2 import IPRoute

from .address.ipv6 import ipv6_netmask_to_prefixlen
from .address.types import AddressFamily

logger = logging.getLogger(__name__)

__all__ = ["Route", "RouteFlags", "RoutingTable", "RouteTable", "IPRoute"]

DEFAULT_TABLE_ID = 254  # This is the default table named as "main" and most of what we do happens here
ip = IPRoute()


class Route:
    def __init__(
        self, network, netmask, gateway=None, interface=None, flags=None,
        table_id=None, preferred_source=None, scope=None,
    ):
        self.network = ipaddress.ip_address(network)
        self.netmask = ipaddress.ip_address(netmask)
        self.gateway = ipaddress.ip_address(gateway) if gateway else None
        self.interface = interface or None
        self.flags = flags or set()
        self.table_id = table_id
        self.scope = scope
        self.preferred_source = preferred_source

    def __getstate__(self):
        return {
            'network': str(self.network),
            'netmask': str(self.netmask),
            'gateway': str(self.gateway) if self.gateway else None,
            'interface': self.interface,
            'flags': [x.name for x in self.flags],
            'table_id': self.table_id,
            'scope': self.scope,
            'preferred_source': self.preferred_source,
        }

    @property
    def af(self):
        if self.network.version == 4:
            return AddressFamily.INET

        if self.network.version == 6:
            return AddressFamily.INET6

        return None

    def __eq__(self, other):
        if not isinstance(other, Route):
            return False

        return (
            self.network == other.network and
            self.netmask == other.netmask and
            self.gateway == other.gateway
        )

    def __hash__(self):
        return hash((self.network, self.netmask, self.gateway))


class RouteTable:
    def __init__(self, table_id, table_name):
        self.table_id = table_id
        self.table_name = table_name

    @property
    def is_reserved(self):
        return self.table_id in (255, 254, 253, 0)

    @property
    def routes(self):
        return RoutingTable().routes_internal(self.table_id)

    def flush_routes(self):
        ip.flush_routes(table=self.table_id)

    def flush_rules(self):
        ip.flush_rules(table=self.table_id)

    def __eq__(self, other):
        return self.table_id == other.table_id

    def __getstate__(self):
        return {
            "id": self.table_id,
            "name": self.table_name,
            "routes": [r.__getstate__() for r in self.routes],
        }


class RouteFlags(enum.IntEnum):
    # include/uapi/linux/route.h

    UP = 0x0001
    GATEWAY = 0x0002
    HOST = 0x0004
    REJECT = 0x0200
    DYNAMIC = 0x0010
    MODIFIED = 0x0020
    # DONE = defs.RTF_DONE
    # XRESOLVE = defs.RTF_XRESOLVE
    # LLINFO = defs.RTF_LLINFO
    # LLDATA = defs.RTF_LLDATA
    STATIC = 0x8000  # no-op
    # BLACKHOLE = defs.RTF_BLACKHOLE
    # PROTO1 = defs.RTF_PROTO1
    # PROTO2 = defs.RTF_PROTO2
    # PROTO3 = defs.RTF_PROTO3
    # PINNED = defs.RTF_PINNED
    # LOCAL = defs.RTF_LOCAL
    # BROADCAST = defs.RTF_BROADCAST
    # MULTICAST = defs.RTF_MULTICAST
    # STICKY = defs.RTF_STICKY


RTM_F_CLONED = 0x200


class RoutingTable:
    @property
    def routes(self):
        return self.routes_internal()

    def routes_internal(self, table_filter=None):
        interfaces = self._interfaces()

        result = []
        for r in ip.get_routes(table=table_filter):
            if r["flags"] & RTM_F_CLONED:
                continue

            attrs = dict(r["attrs"])

            if "RTA_DST" in attrs:
                network = ipaddress.ip_address(attrs["RTA_DST"])
                netmask = ipaddress.ip_network(f"{attrs['RTA_DST']}/{r['dst_len']}").netmask
            else:
                network, netmask = {
                    socket.AF_INET: (ipaddress.IPv4Address(0), ipaddress.IPv4Address(0)),
                    socket.AF_INET6: (ipaddress.IPv6Address(0), ipaddress.IPv6Address(0)),
                }[r["family"]]

            result.append(Route(
                network,
                netmask,
                ipaddress.ip_address(attrs["RTA_GATEWAY"]) if "RTA_GATEWAY" in attrs else None,
                interfaces[attrs["RTA_OIF"]] if "RTA_OIF" in attrs else None,
                table_id=attrs["RTA_TABLE"],
                preferred_source=attrs.get("RTA_PREFSRC"),
                scope=r["scope"],
            ))

        return result

    @property
    def routing_tables(self):
        if not os.path.exists("/etc/iproute2/rt_tables"):
            return {}

        with open("/etc/iproute2/rt_tables", "r") as f:
            return {
                t["name"]: RouteTable(t["id"], t["name"])
                for t in map(lambda v: {"id": int(v.split()[0].strip()), "name": v.split()[1].strip()}, filter(
                    lambda v: v.strip() and not v.startswith("#") and v.split()[0].strip().isdigit(),
                    f.readlines()
                ))
            }

    @property
    def default_route_ipv4(self):
        f = list(filter(lambda r: int(r.network) == 0 and int(r.netmask) == 0 and r.af == AddressFamily.INET,
                        self.routes_internal(DEFAULT_TABLE_ID)))
        return f[0] if len(f) > 0 else None

    @property
    def default_route_ipv6(self):
        f = list(filter(lambda r: int(r.network) == 0 and int(r.netmask) == 0 and r.af == AddressFamily.INET6,
                        self.routes_internal(DEFAULT_TABLE_ID)))
        return f[0] if len(f) > 0 else None

    def add(self, route):
        self._op("add", route)

    def change(self, route):
        self._op("set", route)

    def delete(self, route):
        self._op("delete", route)

    def _interfaces(self):
        return bidict.bidict({i["index"]: dict(i["attrs"]).get("IFLA_IFNAME") for i in ip.get_links()})

    def _op(self, op, route):
        if route.netmask.version == 4:
            prefixlen = ipaddress.ip_network(f"{route.network}/{route.netmask}").prefixlen
        elif route.netmask.version == 6:
            prefixlen = ipv6_netmask_to_prefixlen(str(route.netmask))
        else:
            raise RuntimeError()

        kwargs = dict(dst=f"{route.network}/{prefixlen}", gateway=str(route.gateway) if route.gateway else None)
        for key, value in map(
            lambda v: [v[0], v[1]() if isinstance(v[1], collections.abc.Callable) else v[1]],
            filter(
                lambda v: v[2] if len(v) == 3 else v[1], (
                    ("oif", lambda: self._interfaces().inv[route.interface], route.interface is not None),
                    ("table", route.table_id),
                    ("scope", route.scope),
                    ("prefsrc", route.preferred_source),
                )
            )
        ):
            kwargs[key] = value

        ip.route(op, **kwargs)
