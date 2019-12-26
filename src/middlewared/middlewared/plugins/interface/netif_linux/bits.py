# -*- coding=utf-8 -*-
import enum
import logging

logger = logging.getLogger(__name__)

__all__ = ["InterfaceCapability", "InterfaceFlags", "InterfaceLinkState", "NeighborDiscoveryFlags"]


class InterfaceCapability(enum.IntEnum):
    pass


class InterfaceFlags(enum.IntEnum):
    # include/uapi/linux/if.h

    UP = 1 << 0
    BROADCAST = 1 << 1
    DEBUG = 1 << 2
    LOOPBACK = 1 << 3
    POINTOPOINT = 1 << 4
    # DRV_RUNNING = defs.IFF_DRV_RUNNING
    NOARP = 1 << 7
    PROMISC = 1 << 8
    ALLMULTI = 1 << 9
    # DRV_OACTIVE = defs.IFF_DRV_OACTIVE
    # SIMPLEX = defs.IFF_SIMPLEX
    # LINK0 = defs.IFF_LINK0
    # LINK1 = defs.IFF_LINK1
    # LINK2 = defs.IFF_LINK2
    MULTICAST = 1 << 12
    # CANTCONFIG = defs.IFF_CANTCONFIG
    # PPROMISC = defs.IFF_PPROMISC
    # MONITOR = defs.IFF_MONITOR
    # STATICARP = defs.IFF_STATICARP
    # DYING = defs.IFF_DYING
    # RENAMING = defs.IFF_RENAMING


class InterfaceLinkState(enum.IntEnum):
    LINK_STATE_UNKNOWN = 0
    LINK_STATE_DOWN = 1
    LINK_STATE_UP = 2


class NeighborDiscoveryFlags(enum.IntEnum):
    PERFORMNUD = 0
    ACCEPT_RTADV = 0
    PREFER_SOURCE = 0
    IFDISABLED = 0
    DONT_SET_IFROUTE = 0
    AUTO_LINKLOCAL = 0
    NO_RADR = 0
    NO_PREFER_IFACE = 0
