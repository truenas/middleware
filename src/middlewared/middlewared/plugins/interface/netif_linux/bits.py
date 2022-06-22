from enum import IntEnum

__all__ = ["InterfaceFlags", "InterfaceV6Flags", "InterfaceLinkState", "NeighborDiscoveryFlags"]


class InterfaceFlags(IntEnum):
    # include/uapi/linux/if.h
    UP = 1 << 0  # sysfs
    BROADCAST = 1 << 1  # volatile
    DEBUG = 1 << 2  # sysfs
    LOOPBACK = 1 << 3  # volatile
    POINTOPOINT = 1 << 4  # volatile
    NOTRAILERS = 1 << 5  # sysfs
    RUNNING = 1 << 6  # volatile
    NOARP = 1 << 7  # sysfs
    PROMISC = 1 << 8  # sysfs
    ALLMULTI = 1 << 9  # sysfs
    MASTER = 1 << 10  # volatile
    SLAVE = 1 << 11  # volatile
    MULTICAST = 1 << 12  # sysfs
    PORTSEL = 1 << 13  # sysfs
    AUTOMEDIA = 1 << 14  # sysfs
    DYNAMIC = 1 << 15  # sysfs
    LOWER_UP = 1 << 16
    DORMANT = 1 << 17
    ECHO = 1 << 18


class InterfaceV6Flags(IntEnum):
    # include/uapi/linux/if_addr.h
    TEMPORARY = 0x01
    NODAD = 0x02
    OPTIMISTIC = 0x04
    DADFAILED = 0x08
    HOMEADDRESS = 0x10
    DEPRECATED = 0x20
    TENTATIVE = 0x40
    PERMANENT = 0x80
    MANAGETEMPADDR = 0x100
    NOPREFIXROUTE = 0x200
    MCAUTOJOIN = 0x400
    STABLE_PRIVACY = 0x800


class InterfaceLinkState(IntEnum):
    LINK_STATE_UNKNOWN = 0
    LINK_STATE_DOWN = 1
    LINK_STATE_UP = 2


class NeighborDiscoveryFlags(IntEnum):
    PERFORMNUD = 0
    ACCEPT_RTADV = 0
    PREFER_SOURCE = 0
    IFDISABLED = 0
    DONT_SET_IFROUTE = 0
    AUTO_LINKLOCAL = 0
    NO_RADR = 0
    NO_PREFER_IFACE = 0
