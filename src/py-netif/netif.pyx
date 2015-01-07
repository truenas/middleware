#!/usr/local/bin/python2.7
#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import array
import os
import socket
import netaddr
import sysctl
import enum
import cython
cimport defs
from libc.stdint cimport *
from libc.string cimport strcpy


class RoutingMessageType(enum.IntEnum):
    INVALID = 0
    ADD = defs.RTM_ADD
    DELETE = defs.RTM_DELETE
    CHANGE = defs.RTM_CHANGE
    GET = defs.RTM_GET
    LOSING = defs.RTM_LOSING
    REDIRECT = defs.RTM_REDIRECT
    MISS = defs.RTM_MISS
    LOCK = defs.RTM_LOCK
    RESOLVE = defs.RTM_RESOLVE
    NEWADDR = defs.RTM_NEWADDR
    DELADDR = defs.RTM_DELADDR
    IFINFO = defs.RTM_IFINFO
    NEWMADDR = defs.RTM_NEWMADDR
    DELMADDR = defs.RTM_DELMADDR
    IFANNOUNCE = defs.RTM_IFANNOUNCE
    IEEE80211 = defs.RTM_IEEE80211


class InterfaceAddress(object):
    def __init__(self, af=None, address=None):
        self.af = af
        self.address = address
        self.netmask = None
        self.broadcast = None
        self.dest_address = None
        self.scope = None


cdef class NetworkInterface(object):
    cdef readonly object name
    cdef readonly object addresses

    def __init__(self, name):
        self.name = name
        self.addresses = []

    cdef ioctl(self, uint32_t cmd, void* args):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        defs.ioctl(s.fileno(), cmd, args)
        s.close()

    def __getstate__(self):
        return {
            'name': self.name,
            'addresses': [i.__getstate__() for i in self.addresses]
        }

    def _get_flags(self):
        cdef defs.ifreq ifr
        strcpy(ifr.ifr_name, self.name)
        self.ioctl(defs.SIOCGIFFLAGS, <void*>&ifr)
        return ifr.ifr_ifru.ifru_flags[0]

    property flags:
        def __get__(self):
            pass

    property connected:
        def __get__(self):
            cdef defs.ifmediareq req
            self.ioctl(defs.SIOCGIFMEDIA, <void*>&req)

    property link_address:
        def __get__(self):
            return filter(lambda x: x.af == defs.AF_LINK).pop()

        def __set__(self, address):
            pass

    def add_address(self, address):
        cdef defs.ifaliasreq req
        #cdef defs.in6_ifaliasreq req6

        if address.version == 4:
            self.ioctl(defs.SIOCAIFADDR, <void*>&req)
            self.addresses.append(address)
        elif address.version == 6:
            self.ioctl(defs.SIOCAIFADDR, <void*>&req)
            self.addresses.append(address)
        else:
            raise NotImplementedError()

    def remove_address(self, address):
        cdef defs.ifaliasreq req
        #cdef defs.in6_ifaliasreq req6

        if address.version == 4:
            self.ioctl(defs.SIOCAIFADDR, <void*>&req)
            self.addresses.append(address)
        elif address.version == 6:
            self.ioctl(defs.SIOCAIFADDR, <void*>&req)
            self.addresses.append(address)
        else:
            raise NotImplementedError()

    def down(self):
        cdef defs.ifreq ifr
        strcpy(ifr.ifr_name, self.name)
        ifr.ifr_ifru.ifru_flags[0] = self._get_flags() & ~defs.IFF_UP
        self.ioctl(defs.SIOCSIFFLAGS, <void*>&ifr)

    def up(self):
        cdef defs.ifreq ifr
        strcpy(ifr.ifr_name, self.name)
        ifr.ifr_ifru.ifru_flags[0] = self._get_flags() | defs.IFF_UP
        self.ioctl(defs.SIOCSIFFLAGS, <void*>&ifr)


class LaggInterface(NetworkInterface):
    pass


class CarpInterface(NetworkInterface):
    pass



cdef class RoutingPacket(object):
    cdef readonly object data
    cdef char *buffer
    cdef defs.rt_msghdr *rt_msg

    def __init__(self, data):
        self.data = data
        self.buffer = <char*>data
        self.rt_msg = <defs.rt_msghdr*>self.buffer

    def __getstate__(self):
        return {
            'type': self.type,
            'version': self.version,
            'length': self.length
        }

    def _align_sa_len(self, length):
        return 1 + (length | cython.sizeof(long) - 1)

    def _parse_sockaddrs(self, start_offset, count):
        cdef defs.sockaddr* sa
        cdef defs.sockaddr_in* sin
        cdef defs.sockaddr_in6* sin6

        ptr = start_offset
        result = []

        for i in range(0, count):
            sa = <defs.sockaddr*>&self.buffer[ptr]
            ptr += self._align_sa_len(sa.sa_len)

            if sa.sa_family == defs.AF_INET:
                sin = <defs.sockaddr_in*>sa
                result.append(netaddr.IPAddress(sin.sin_addr.s_addr))

            if sa.sa_family == defs.AF_INET6:
                sin6 = <defs.sockaddr_in6*>sa
                result.append(netaddr.IPAddress(socket.inet_ntop(socket.AF_INET6, sin6.sin6_addr.s6_addr[:16])))

        return result

    property type:
        def __get__(self):
            return RoutingMessageType(self.rt_msg.rtm_type)

    property version:
        def __get__(self):
            return self.rt_msg.rtm_version

    property length:
        def __get__(self):
            return self.rt_msg.rtm_msglen


cdef class InterfaceAnnounceMessage(RoutingPacket):
    cdef defs.if_announcemsghdr *header

    def __init__(self, packet):
        super(InterfaceAnnounceMessage, self).__init__(packet)
        self.header = <defs.if_announcemsghdr*>self.buffer

    def __getstate__(self):
        state = super(InterfaceAnnounceMessage, self).__getstate__()
        state.update({
            'interface': self.interface
        })

        return state

    property interface:
        def __get__(self):
            return self.header.ifan_name


cdef class InterfaceInfoMessage(RoutingPacket):
    cdef defs.ifa_msghdr *header

    def __init__(self, packet):
        super(InterfaceInfoMessage, self).__init__(packet)
        self.header = <defs.ifa_msghdr*>self.buffer

    def __getstate__(self):
        state = super(InterfaceInfoMessage, self).__getstate__()

        return state



cdef class InterfaceAddrMessage(RoutingPacket):
    cdef defs.ifa_msghdr *header

    def __init__(self, packet):
        super(InterfaceAddrMessage, self).__init__(packet)
        self.header = <defs.ifa_msghdr*>self.buffer
        self.addrs = self._parse_sockaddrs(cython.sizeof(defs.rt_msghdr), bin(self.addrs_count).count('1'))

    def __getstate__(self):
        state = super(InterfaceAddrMessage, self).__getstate__()

        return state

    property addrs_count:
        def __get__(self):
            return self.rt_msg.rtm_addrs


cdef class RoutingMessage(RoutingPacket):
    cdef readonly object addrs
    cdef int addrs_mask

    def __init__(self, packet=None):
        super(RoutingMessage, self).__init__(packet)
        self.addrs_mask = self.rt_msg.rtm_addrs
        self.addrs = self._parse_sockaddrs(cython.sizeof(defs.rt_msghdr), bin(self.addrs_mask).count('1'))

    def __getstate__(self):
        state = super(RoutingMessage, self).__getstate__()
        state.update({
            'network': self.network,
            'gateway': self.gateway
        })

        return state

    property errno:
        def __get__(self):
            return self.rt_msg.rtm_errno

    property network:
        def __get__(self):
            if self.addrs_mask & defs.RTAX_DST and self.addrs_mask & defs.RTAX_NETMASK:
                return netaddr.IPNetwork('{0}/{1}'.format(
                    self.addrs[defs.RTAX_DST],
                    self.addrs[defs.RTAX_NETMASK]))

            return None

        def __set__(self, value):
            pass

    property gateway:
        def __get__(self):
            if self.addrs_mask & defs.RTAX_GATEWAY:
                return self.addrs[defs.RTAX_GATEWAY]

            return None

        def __set__(self, value):
            pass


class Route(object):
    def __init__(self):
        self.af = None
        self.network = None
        self.gateway = None


    def __getstate__(self):
        return {
            'af': self.af,
            'network': str(self.network),
            'gateway': str(self.gateway)
        }

class RoutingTable(object):
    def __init__(self):
        pass

    def __send_message(self, buf):
        sock = socket.socket(socket.AF_ROUTE, socket.SOCK_RAW, 0)
        os.write(sock.fileno(), buf)
        sock.close()

    @property
    def routes(self):
        data = sysctl.sysctl([defs.CTL_NET, defs.AF_ROUTE, 0, 0, defs.NET_RT_DUMP, 0])
        data = array.array('b', data).tostring()
        ptr = 0

        while True:
            msg = RoutingMessage(data[ptr:])
            route = Route()
            ptr += msg.length

            yield route

    def add(self, af, network, gateway):
        pass

    def delete(self, af, network):
        pass


class RoutingSocketEventSource(object):
    def __init__(self):
        self.socket = None

    def open(self):
         self.socket = socket.socket(socket.AF_ROUTE, socket.SOCK_RAW, 0)

    def close(self):
        self.socket.close()

    def read_message(self):
        cdef char* buffer
        cdef defs.rt_msghdr* rt_msg

        packet = os.read(self.socket.fileno(), 1024)
        buffer = <char*>packet
        rt_msg = <defs.rt_msghdr*>buffer

        if rt_msg.rtm_type in (RoutingMessageType.IFANNOUNCE, RoutingMessageType.IEEE80211):
            return InterfaceAnnounceMessage(packet)

        if rt_msg.rtm_type == RoutingMessageType.IFINFO:
            return InterfaceInfoMessage(packet)

        if rt_msg.rtm_type in (RoutingMessageType.NEWADDR, RoutingMessageType.DELADDR):
            return InterfaceAddrMessage(packet)

        return RoutingMessage(packet)


def list_interfaces(name=None):
    cdef defs.ifaddrs* ifa
    cdef defs.sockaddr_in* sin
    cdef defs.sockaddr_in6* sin6
    cdef defs.sockaddr_dl* sdl
    cdef defs.sockaddr* sa

    if defs.getifaddrs(&ifa) != 0:
        return None

    result = {}

    while ifa:
        name = ifa.ifa_name

        if name not in result:
            result[name] = NetworkInterface(name)

        nic = result[name]
        sa = ifa.ifa_addr
        addr = InterfaceAddress(sa.sa_family)

        if sa.sa_family == defs.AF_INET:
            if ifa.ifa_addr != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_addr
                addr.address = netaddr.IPAddress(sin.sin_addr.s_addr)

            if ifa.ifa_netmask != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_netmask
                addr.netmask = netaddr.IPAddress(sin.sin_addr.s_addr)

            if ifa.ifa_broadaddr != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_broadaddr
                addr.broadcast = netaddr.IPAddress(sin.sin_addr.s_addr)

            if ifa.ifa_dstaddr != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_dstaddr
                addr.dest_address = netaddr.IPAddress(sin.sin_addr.s_addr)

        if sa.sa_family == defs.AF_INET6:
            if ifa.ifa_addr != NULL:
                sin6 = <defs.sockaddr_in6*>ifa.ifa_addr
                addr.address = netaddr.IPAddress(socket.inet_ntop(socket.AF_INET6, sin6.sin6_addr.s6_addr[:16]))
                if str(addr.address).startswith('fe80:'):
                    addr.scope = sin6.sin6_scope_id

            if ifa.ifa_netmask != NULL:
                sin6 = <defs.sockaddr_in6*>ifa.ifa_addr
                addr.netmask = netaddr.IPAddress(socket.inet_ntop(socket.AF_INET6, sin6.sin6_addr.s6_addr[:16]))

        if sa.sa_family == defs.AF_LINK:
            if ifa.ifa_addr != NULL:
                sdl = <defs.sockaddr_dl*>ifa.ifa_addr
                addr.address = ":".join(["{0:02x}".format(ord(x)) for x in sdl.sdl_data[sdl.sdl_nlen+1:sdl.sdl_nlen+sdl.sdl_alen+1]])

        nic.addresses.append(addr)

        if ifa.ifa_next:
            ifa = ifa.ifa_next
        else:
            break

    defs.freeifaddrs(ifa)
    return result


def get_interface(name):
    return list_interfaces(name)[name]


def create_interface(name):
    cdef defs.ifreq ifr
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    strcpy(ifr.ifr_name, name)
    defs.ioctl(s.fileno(), defs.SIOCIFCREATE, <void*>&ifr)
    s.close()
    return ifr.ifr_name


def destroy_interface(name):
    cdef defs.ifreq ifr
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    strcpy(ifr.ifr_name, name)
    defs.ioctl(s.fileno(), defs.SIOCIFDESTROY, <void*>&ifr)
    s.close()
    return ifr.ifr_name