# -*- coding=utf-8 -*-
import enum
import ipaddress
import logging

logger = logging.getLogger(__name__)

__all__ = ['AddressFamily', 'LinkAddress', 'InterfaceAddress']


class AddressFamily(enum.IntEnum):
    UNIX = 1
    INET = 2
    # IMPLINK = defs.AF_IMPLINK
    # PUP = defs.AF_PUP
    # CHAOS = defs.AF_CHAOS
    # NETBIOS = defs.AF_NETBIOS
    # ISO = defs.AF_ISO
    # OSI = defs.AF_OSI
    # ECMA = defs.AF_ECMA
    # DATAKIT = defs.AF_DATAKIT
    # CCITT = defs.AF_CCITT
    # SNA = defs.AF_SNA
    # DECnet = defs.AF_DECnet
    # DLI = defs.AF_DLI
    # LAT = defs.AF_LAT
    # HYLINK = defs.AF_HYLINK
    # APPLETALK = defs.AF_APPLETALK
    # ROUTE = defs.AF_ROUTE
    LINK = 17
    # COIP = defs.AF_COIP
    # CNT = defs.AF_CNT
    # IPX = defs.AF_IPX
    # SIP = defs.AF_SIP
    # ISDN = defs.AF_ISDN
    # E164 = defs.AF_E164
    INET6 = 10
    # NATM = defs.AF_NATM
    # ATM = defs.AF_ATM
    # NETGRAPH = defs.AF_NETGRAPH
    # SLOW = defs.AF_SLOW
    # SCLUSTER = defs.AF_SCLUSTER
    # ARP = defs.AF_ARP
    # BLUETOOTH = defs.AF_BLUETOOTH
    # IEEE80211 = defs.AF_IEEE80211
    # INET_SDP = defs.AF_INET_SDP
    # INET6_SDP = defs.AF_INET6_SDP


class LinkAddress(object):
    def __init__(self, ifname=None, address=None):
        self.ifname = ifname
        self.address = address

    def __str__(self):
        return self.address

    def __getstate__(self):
        return {
            'ifname': self.ifname,
            'address': self.address
        }

    def __hash__(self):
        return hash((self.ifname, self.address))

    def __eq__(self, other):
        return \
            self.ifname == other.ifname and \
            self.address == other.address

    def __ne__(self, other):
        return not self == other


class InterfaceAddress(object):
    def __init__(self, af=None, address=None):
        self.af = af

        if isinstance(address, (ipaddress.IPv4Interface, ipaddress.IPv6Interface)):
            self.address = address.ip
            self.netmask = address.netmask
            self.broadcast = address.network.broadcast_address
        else:
            self.address = address
            self.netmask = None
            self.broadcast = None

        self.dest_address = None
        self.scope = None
        self.ipv6_flags = None
        self.vhid = None

        self.received_packets = self.received_errors = self.received_dropped_packets = self.received_bytes = \
            self.sent_packets = self.sent_errors = self.sent_bytes = self.collisions = self.sent_dropped_packets = None

    def __str__(self):
        return u'{0}/{1}'.format(self.address, self.netmask)

    def __hash__(self):
        return hash((self.af, self.address, self.netmask, self.broadcast, self.dest_address))

    def __getstate__(self, stats=False):
        ret = {
            'type': self.af.name,
            'address': self.address.address if type(self.address) is LinkAddress else str(self.address)
        }

        if stats:
            ret['stats'] = {
                'received_packets': self.received_packets,
                'received_errors': self.received_errors,
                'received_dropped_packets': self.received_dropped_packets,
                'received_bytes': self.received_bytes,
                'sent_packets': self.sent_packets,
                'sent_errors': self.sent_errors,
                'sent_bytes': self.sent_bytes,
                'collisions': self.collisions,
                'sent_dropped_packets': self.sent_dropped_packets,
            }

        if self.netmask:
            # XXX yuck!
            ret['netmask'] = bin(int(self.netmask)).count('1')

        if self.broadcast:
            ret['broadcast'] = str(self.broadcast)

        return ret

    def __eq__(self, other):
        return \
            self.af == other.af and \
            self.address == other.address and \
            self.netmask == other.netmask and \
            self.broadcast == other.broadcast and \
            self.dest_address == other.dest_address and \
            self.vhid == other.vhid

    def __ne__(self, other):
        return not self == other
