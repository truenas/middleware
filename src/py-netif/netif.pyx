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
import ipaddress
import sysctl
import enum
import cython
cimport defs
from libc.errno cimport *
from libc.stdint cimport *
from libc.string cimport strcpy, strerror, memset, memcpy
from libc.stdlib cimport malloc, realloc, free


CLONED_PREFIXES = ['lo', 'tun', 'tap', 'bridge', 'epair', 'carp', 'vlan']


class AddressFamily(enum.IntEnum):
    UNIX = defs.AF_UNIX
    INET = defs.AF_INET
    IMPLINK = defs.AF_IMPLINK
    PUP = defs.AF_PUP
    CHAOS = defs.AF_CHAOS
    NETBIOS = defs.AF_NETBIOS
    ISO = defs.AF_ISO
    OSI = defs.AF_OSI
    ECMA = defs.AF_ECMA
    DATAKIT = defs.AF_DATAKIT
    CCITT = defs.AF_CCITT
    SNA = defs.AF_SNA
    DECnet = defs.AF_DECnet
    DLI = defs.AF_DLI
    LAT = defs.AF_LAT
    HYLINK = defs.AF_HYLINK
    APPLETALK = defs.AF_APPLETALK
    ROUTE = defs.AF_ROUTE
    LINK = defs.AF_LINK
    COIP = defs.AF_COIP
    CNT = defs.AF_CNT
    IPX = defs.AF_IPX
    SIP = defs.AF_SIP
    ISDN = defs.AF_ISDN
    E164 = defs.AF_E164
    INET6 = defs.AF_INET6
    NATM = defs.AF_NATM
    ATM = defs.AF_ATM
    NETGRAPH = defs.AF_NETGRAPH
    SLOW = defs.AF_SLOW
    SCLUSTER = defs.AF_SCLUSTER
    ARP = defs.AF_ARP
    BLUETOOTH = defs.AF_BLUETOOTH
    IEEE80211 = defs.AF_IEEE80211
    INET_SDP = defs.AF_INET_SDP
    INET6_SDP = defs.AF_INET6_SDP


class RouteFlags(enum.IntEnum):
    UP = defs.RTF_UP
    GATEWAY = defs.RTF_GATEWAY
    HOST = defs.RTF_HOST
    REJECT = defs.RTF_REJECT
    DYNAMIC = defs.RTF_DYNAMIC
    MODIFIED = defs.RTF_MODIFIED
    DONE = defs.RTF_DONE
    XRESOLVE = defs.RTF_XRESOLVE
    LLINFO = defs.RTF_LLINFO
    LLDATA = defs.RTF_LLDATA
    STATIC = defs.RTF_STATIC
    BLACKHOLE = defs.RTF_BLACKHOLE
    PROTO1 = defs.RTF_PROTO1
    PROTO2 = defs.RTF_PROTO2
    PROTO3 = defs.RTF_PROTO3
    PINNED = defs.RTF_PINNED
    LOCAL = defs.RTF_LOCAL
    BROADCAST = defs.RTF_BROADCAST
    MULTICAST = defs.RTF_MULTICAST
    STICKY = defs.RTF_STICKY


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


class InterfaceFlags(enum.IntEnum):
    UP = defs.IFF_UP
    BROADCAST = defs.IFF_BROADCAST
    DEBUG = defs.IFF_DEBUG
    LOOPBACK = defs.IFF_LOOPBACK
    POINTOPOINT = defs.IFF_POINTOPOINT
    DRV_RUNNING = defs.IFF_DRV_RUNNING
    NOARP = defs.IFF_NOARP
    PROMISC = defs.IFF_PROMISC
    ALLMULTI = defs.IFF_ALLMULTI
    DRV_OACTIVE = defs.IFF_DRV_OACTIVE
    SIMPLEX = defs.IFF_SIMPLEX
    LINK0 = defs.IFF_LINK0
    LINK1 = defs.IFF_LINK1
    LINK2 = defs.IFF_LINK2
    MULTICAST = defs.IFF_MULTICAST
    CANTCONFIG = defs.IFF_CANTCONFIG
    PPROMISC = defs.IFF_PPROMISC
    MONITOR = defs.IFF_MONITOR
    STATICARP = defs.IFF_STATICARP
    DYING = defs.IFF_DYING
    RENAMING = defs.IFF_RENAMING
    
    
class InterfaceType(enum.IntEnum):
    OTHER = defs.IFT_OTHER
    I1822 = defs.IFT_1822
    HDH1822 = defs.IFT_HDH1822
    X25DDN = defs.IFT_X25DDN
    X25 = defs.IFT_X25
    ETHER = defs.IFT_ETHER
    ISO88023 = defs.IFT_ISO88023
    ISO88024 = defs.IFT_ISO88024
    ISO88025 = defs.IFT_ISO88025
    ISO88026 = defs.IFT_ISO88026
    STARLAN = defs.IFT_STARLAN
    P10 = defs.IFT_P10
    P80 = defs.IFT_P80
    HY = defs.IFT_HY
    FDDI = defs.IFT_FDDI
    LAPB = defs.IFT_LAPB
    SDLC = defs.IFT_SDLC
    T1 = defs.IFT_T1
    CEPT = defs.IFT_CEPT
    ISDNBASIC = defs.IFT_ISDNBASIC
    ISDNPRIMARY = defs.IFT_ISDNPRIMARY
    PTPSERIAL = defs.IFT_PTPSERIAL
    PPP = defs.IFT_PPP
    LOOP = defs.IFT_LOOP
    EON = defs.IFT_EON
    XETHER = defs.IFT_XETHER
    NSIP = defs.IFT_NSIP
    SLIP = defs.IFT_SLIP
    ULTRA = defs.IFT_ULTRA
    DS3 = defs.IFT_DS3
    SIP = defs.IFT_SIP
    FRELAY = defs.IFT_FRELAY
    RS232 = defs.IFT_RS232
    PARA = defs.IFT_PARA
    ARCNET = defs.IFT_ARCNET
    ARCNETPLUS = defs.IFT_ARCNETPLUS
    ATM = defs.IFT_ATM
    MIOX25 = defs.IFT_MIOX25
    SONET = defs.IFT_SONET
    X25PLE = defs.IFT_X25PLE
    ISO88022LLC = defs.IFT_ISO88022LLC
    LOCALTALK = defs.IFT_LOCALTALK
    SMDSDXI = defs.IFT_SMDSDXI
    FRELAYDCE = defs.IFT_FRELAYDCE
    V35 = defs.IFT_V35
    HSSI = defs.IFT_HSSI
    HIPPI = defs.IFT_HIPPI
    MODEM = defs.IFT_MODEM
    AAL5 = defs.IFT_AAL5
    SONETPATH = defs.IFT_SONETPATH
    SONETVT = defs.IFT_SONETVT
    SMDSICIP = defs.IFT_SMDSICIP
    PROPVIRTUAL = defs.IFT_PROPVIRTUAL
    PROPMUX = defs.IFT_PROPMUX
    IEEE80212 = defs.IFT_IEEE80212
    FIBRECHANNEL = defs.IFT_FIBRECHANNEL
    HIPPIINTERFACE = defs.IFT_HIPPIINTERFACE
    FRAMERELAYINTERCONNECT = defs.IFT_FRAMERELAYINTERCONNECT
    AFLANE8023 = defs.IFT_AFLANE8023
    AFLANE8025 = defs.IFT_AFLANE8025
    CCTEMUL = defs.IFT_CCTEMUL
    FASTETHER = defs.IFT_FASTETHER
    ISDN = defs.IFT_ISDN
    V11 = defs.IFT_V11
    V36 = defs.IFT_V36
    G703AT64K = defs.IFT_G703AT64K
    G703AT2MB = defs.IFT_G703AT2MB
    QLLC = defs.IFT_QLLC
    FASTETHERFX = defs.IFT_FASTETHERFX
    CHANNEL = defs.IFT_CHANNEL
    IEEE80211 = defs.IFT_IEEE80211
    IBM370PARCHAN = defs.IFT_IBM370PARCHAN
    ESCON = defs.IFT_ESCON
    DLSW = defs.IFT_DLSW
    ISDNS = defs.IFT_ISDNS
    ISDNU = defs.IFT_ISDNU
    LAPD = defs.IFT_LAPD
    IPSWITCH = defs.IFT_IPSWITCH
    RSRB = defs.IFT_RSRB
    ATMLOGICAL = defs.IFT_ATMLOGICAL
    DS0 = defs.IFT_DS0
    DS0BUNDLE = defs.IFT_DS0BUNDLE
    BSC = defs.IFT_BSC
    ASYNC = defs.IFT_ASYNC
    CNR = defs.IFT_CNR
    ISO88025DTR = defs.IFT_ISO88025DTR
    EPLRS = defs.IFT_EPLRS
    ARAP = defs.IFT_ARAP
    PROPCNLS = defs.IFT_PROPCNLS
    HOSTPAD = defs.IFT_HOSTPAD
    TERMPAD = defs.IFT_TERMPAD
    FRAMERELAYMPI = defs.IFT_FRAMERELAYMPI
    X213 = defs.IFT_X213
    ADSL = defs.IFT_ADSL
    RADSL = defs.IFT_RADSL
    SDSL = defs.IFT_SDSL
    VDSL = defs.IFT_VDSL
    ISO88025CRFPINT = defs.IFT_ISO88025CRFPINT
    MYRINET = defs.IFT_MYRINET
    VOICEEM = defs.IFT_VOICEEM
    VOICEFXO = defs.IFT_VOICEFXO
    VOICEFXS = defs.IFT_VOICEFXS
    VOICEENCAP = defs.IFT_VOICEENCAP
    VOICEOVERIP = defs.IFT_VOICEOVERIP
    ATMDXI = defs.IFT_ATMDXI
    ATMFUNI = defs.IFT_ATMFUNI
    ATMIMA = defs.IFT_ATMIMA
    PPPMULTILINKBUNDLE = defs.IFT_PPPMULTILINKBUNDLE
    IPOVERCDLC = defs.IFT_IPOVERCDLC
    IPOVERCLAW = defs.IFT_IPOVERCLAW
    STACKTOSTACK = defs.IFT_STACKTOSTACK
    VIRTUALIPADDRESS = defs.IFT_VIRTUALIPADDRESS
    MPC = defs.IFT_MPC
    IPOVERATM = defs.IFT_IPOVERATM
    ISO88025FIBER = defs.IFT_ISO88025FIBER
    TDLC = defs.IFT_TDLC
    GIGABITETHERNET = defs.IFT_GIGABITETHERNET
    HDLC = defs.IFT_HDLC
    LAPF = defs.IFT_LAPF
    V37 = defs.IFT_V37
    X25MLP = defs.IFT_X25MLP
    X25HUNTGROUP = defs.IFT_X25HUNTGROUP
    TRANSPHDLC = defs.IFT_TRANSPHDLC
    INTERLEAVE = defs.IFT_INTERLEAVE
    FAST = defs.IFT_FAST
    IP = defs.IFT_IP
    DOCSCABLEMACLAYER = defs.IFT_DOCSCABLEMACLAYER
    DOCSCABLEDOWNSTREAM = defs.IFT_DOCSCABLEDOWNSTREAM
    DOCSCABLEUPSTREAM = defs.IFT_DOCSCABLEUPSTREAM
    A12MPPSWITCH = defs.IFT_A12MPPSWITCH
    TUNNEL = defs.IFT_TUNNEL
    COFFEE = defs.IFT_COFFEE
    CES = defs.IFT_CES
    ATMSUBINTERFACE = defs.IFT_ATMSUBINTERFACE
    L2VLAN = defs.IFT_L2VLAN
    L3IPVLAN = defs.IFT_L3IPVLAN
    L3IPXVLAN = defs.IFT_L3IPXVLAN
    DIGITALPOWERLINE = defs.IFT_DIGITALPOWERLINE
    MEDIAMAILOVERIP = defs.IFT_MEDIAMAILOVERIP
    DTM = defs.IFT_DTM
    DCN = defs.IFT_DCN
    IPFORWARD = defs.IFT_IPFORWARD
    MSDSL = defs.IFT_MSDSL
    IEEE1394 = defs.IFT_IEEE1394
    IFGSN = defs.IFT_IFGSN
    DVBRCCMACLAYER = defs.IFT_DVBRCCMACLAYER
    DVBRCCDOWNSTREAM = defs.IFT_DVBRCCDOWNSTREAM
    DVBRCCUPSTREAM = defs.IFT_DVBRCCUPSTREAM
    ATMVIRTUAL = defs.IFT_ATMVIRTUAL
    MPLSTUNNEL = defs.IFT_MPLSTUNNEL
    SRP = defs.IFT_SRP
    VOICEOVERATM = defs.IFT_VOICEOVERATM
    VOICEOVERFRAMERELAY = defs.IFT_VOICEOVERFRAMERELAY
    IDSL = defs.IFT_IDSL
    COMPOSITELINK = defs.IFT_COMPOSITELINK
    SS7SIGLINK = defs.IFT_SS7SIGLINK
    PROPWIRELESSP2P = defs.IFT_PROPWIRELESSP2P
    FRFORWARD = defs.IFT_FRFORWARD
    RFC1483 = defs.IFT_RFC1483
    USB = defs.IFT_USB
    IEEE8023ADLAG = defs.IFT_IEEE8023ADLAG
    BGPPOLICYACCOUNTING = defs.IFT_BGPPOLICYACCOUNTING
    FRF16MFRBUNDLE = defs.IFT_FRF16MFRBUNDLE
    H323GATEKEEPER = defs.IFT_H323GATEKEEPER
    H323PROXY = defs.IFT_H323PROXY
    MPLS = defs.IFT_MPLS
    MFSIGLINK = defs.IFT_MFSIGLINK
    HDSL2 = defs.IFT_HDSL2
    SHDSL = defs.IFT_SHDSL
    DS1FDL = defs.IFT_DS1FDL
    POS = defs.IFT_POS
    DVBASILN = defs.IFT_DVBASILN
    DVBASIOUT = defs.IFT_DVBASIOUT
    PLC = defs.IFT_PLC
    NFAS = defs.IFT_NFAS
    TR008 = defs.IFT_TR008
    GR303RDT = defs.IFT_GR303RDT
    GR303IDT = defs.IFT_GR303IDT
    ISUP = defs.IFT_ISUP
    PROPDOCSWIRELESSMACLAYER = defs.IFT_PROPDOCSWIRELESSMACLAYER
    PROPDOCSWIRELESSDOWNSTREAM = defs.IFT_PROPDOCSWIRELESSDOWNSTREAM
    PROPDOCSWIRELESSUPSTREAM = defs.IFT_PROPDOCSWIRELESSUPSTREAM
    HIPERLAN2 = defs.IFT_HIPERLAN2
    PROPBWAP2MP = defs.IFT_PROPBWAP2MP
    SONETOVERHEADCHANNEL = defs.IFT_SONETOVERHEADCHANNEL
    DIGITALWRAPPEROVERHEADCHANNEL = defs.IFT_DIGITALWRAPPEROVERHEADCHANNEL
    AAL2 = defs.IFT_AAL2
    RADIOMAC = defs.IFT_RADIOMAC
    ATMRADIO = defs.IFT_ATMRADIO
    IMT = defs.IFT_IMT
    MVL = defs.IFT_MVL
    REACHDSL = defs.IFT_REACHDSL
    FRDLCIENDPT = defs.IFT_FRDLCIENDPT
    ATMVCIENDPT = defs.IFT_ATMVCIENDPT
    OPTICALCHANNEL = defs.IFT_OPTICALCHANNEL
    OPTICALTRANSPORT = defs.IFT_OPTICALTRANSPORT
    INFINIBAND = defs.IFT_INFINIBAND
    BRIDGE = defs.IFT_BRIDGE
    STF = defs.IFT_STF
    GIF = defs.IFT_GIF
    PVC = defs.IFT_PVC
    FAITH = defs.IFT_FAITH
    ENC = defs.IFT_ENC
    PFLOG = defs.IFT_PFLOG
    PFSYNC = defs.IFT_PFSYNC


class InterfaceLinkState(enum.IntEnum):
    LINK_STATE_UNKNOWN = defs.LINK_STATE_UNKNOWN
    LINK_STATE_DOWN = defs.LINK_STATE_DOWN
    LINK_STATE_UP = defs.LINK_STATE_UP


class InterfaceAnnounceType(enum.IntEnum):
    ARRIVAL = defs.IFAN_ARRIVAL
    DEPARTURE = defs.IFAN_DEPARTURE


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
        self.address = address
        self.netmask = None
        self.broadcast = None
        self.dest_address = None
        self.scope = None

    def __str__(self):
        return u'{0}/{1}'.format(self.address, self.netmask)

    def __hash__(self):
        return hash((self.af, self.address, self.netmask, self.broadcast, self.dest_address))

    def __eq__(self, other):
        return \
            self.af == other.af and \
            self.address == other.address and \
            self.netmask == other.netmask and \
            self.broadcast == other.broadcast and \
            self.dest_address == other.dest_address

    def __ne__(self, other):
        return not self == other


cdef class NetworkInterface(object):
    cdef readonly object name
    cdef public object type
    cdef readonly object addresses

    def __init__(self, name):
        self.name = name
        self.addresses = []

    cdef int ioctl(self, uint32_t cmd, void* args):
        cdef int result
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        result = defs.ioctl(s.fileno(), cmd, args)
        s.close()
        return result

    cdef aliasreq(self, address, uint32_t cmd):
        cdef defs.sockaddr_in *sin
        cdef defs.sockaddr_in6 *sin6
        cdef defs.ifaliasreq req
        #cdef defs.in6_ifaliasreq req6

        if address.af == AddressFamily.INET:
            memset(&req, 0, cython.sizeof(req))
            strcpy(req.ifra_name, self.name)

            # Address
            sin = <defs.sockaddr_in*>&req.ifra_addr
            sin.sin_family = defs.AF_INET
            sin.sin_len = cython.sizeof(defs.sockaddr_in)
            sin.sin_addr.s_addr = socket.ntohl(int(address.address))

            # Netmask
            sin = <defs.sockaddr_in*>&req.ifra_mask
            sin.sin_family = defs.AF_INET
            sin.sin_len = cython.sizeof(defs.sockaddr_in)
            sin.sin_addr.s_addr = socket.ntohl(int(address.netmask))

            # Broadcast
            if address.broadcast:
                sin = <defs.sockaddr_in*>&req.ifra_broadaddr
                sin.sin_family = defs.AF_INET
                sin.sin_len = cython.sizeof(defs.sockaddr_in)
                sin.sin_addr.s_addr = socket.ntohl(int(address.broadcast))

            if self.ioctl(cmd, <void*>&req) == -1:
                raise OSError(errno, strerror(errno))

            self.addresses.append(address)
        elif address.af == AddressFamily.INET6:
            self.ioctl(cmd, <void*>&req)
            self.addresses.append(address)
        else:
            raise NotImplementedError()

    def __getstate__(self):
        return {
            'name': self.name,
            'addresses': [i.__getstate__() for i in self.addresses]
        }

    cdef uint16_t _get_flags(self):
        cdef defs.ifreq ifr
        memset(&ifr, 0, cython.sizeof(ifr))
        strcpy(ifr.ifr_name, self.name)
        if self.ioctl(defs.SIOCGIFFLAGS, <void*>&ifr) == -1:
            raise OSError(errno, strerror(errno))
        return ifr.ifr_ifru.ifru_flags[0]

    property cloned:
        def __get__(self):
            for i in CLONED_PREFIXES:
                if self.name.startswith(i):
                    return True

            return False

    property flags:
        def __get__(self):
            return bitmask_to_set(self._get_flags(), InterfaceFlags)

    property mtu:
        def __get__(self):
            cdef defs.ifreq ifr
            memset(&ifr, 0, cython.sizeof(ifr))
            strcpy(ifr.ifr_name, self.name)
            ifr.ifr_ifru.ifru_flags[0] = self._get_flags() & ~defs.IFF_UP
            if self.ioctl(defs.SIOCGIFMTU, <void*>&ifr) == -1:
                raise OSError(errno, strerror(errno))
            return ifr.ifr_ifru.ifru_mtu

        def __set__(self, mtu):
            raise NotImplementedError()

    property link_state:
        def __get__(self):
            cdef defs.ifmediareq ifm
            memset(&ifm, 0, cython.sizeof(ifm))
            strcpy(ifm.ifm_name, self.name)
            if self.ioctl(defs.SIOCGIFMEDIA, <void*>&ifm) == -1:
                if errno != 22: # Invalid argument
                    raise OSError(errno, strerror(errno))

            if ifm.ifm_status & defs.IFM_AVALID:
                if ifm.ifm_status & defs.IFM_ACTIVE:
                    return InterfaceLinkState.LINK_STATE_UP
                else:
                    return InterfaceLinkState.LINK_STATE_DOWN
            else:
                return InterfaceLinkState.LINK_STATE_UNKNOWN

    property link_address:
        def __get__(self):
            return filter(lambda x: x.af == defs.AF_LINK, self.addresses).pop()

        def __set__(self, address):
            raise NotImplementedError()

    def add_address(self, address):
        self.aliasreq(address, defs.SIOCAIFADDR)

    def remove_address(self, address):
        self.aliasreq(address, defs.SIOCDIFADDR)

    def down(self):
        cdef defs.ifreq ifr
        memset(&ifr, 0, cython.sizeof(ifr))
        strcpy(ifr.ifr_name, self.name)
        ifr.ifr_ifru.ifru_flags[0] = self._get_flags() & ~defs.IFF_UP
        if self.ioctl(defs.SIOCSIFFLAGS, <void*>&ifr) == -1:
            raise OSError(errno, strerror(errno))

    def up(self):
        cdef defs.ifreq ifr
        memset(&ifr, 0, cython.sizeof(ifr))
        strcpy(ifr.ifr_name, self.name)
        ifr.ifr_ifru.ifru_flags[0] = self._get_flags() | defs.IFF_UP
        if self.ioctl(defs.SIOCSIFFLAGS, <void*>&ifr) == -1:
            raise OSError(errno, strerror(errno))


class LaggInterface(NetworkInterface):
    pass


class CarpInterface(NetworkInterface):
    pass


class BridgeInterface(NetworkInterface):
    def add_member(self, name):
        pass

    def del_member(self, name):
        pass


cdef class VlanInterface(NetworkInterface):
    def __getstate__(self):
        state = super(VlanInterface, self).__getstate__()
        state.update({
            'parent': self.parent,
            'tag': self.tag
        })

        return state

    def configure(self, parent, tag):
        cdef defs.ifreq ifr
        cdef defs.vlanreq vlr

        memset(&vlr, 0, cython.sizeof(ifr))
        strcpy(ifr.ifr_name, self.name)
        strcpy(vlr.vlr_parent, parent)
        vlr.vlr_tag = tag
        ifr.ifr_ifru.ifru_data = <defs.caddr_t>&vlr

        if self.ioctl(defs.SIOCSETVLAN, <void*>&ifr) == -1:
            raise OSError(errno, strerror(errno))

    def unconfigure(self):
        cdef defs.ifreq ifr
        cdef defs.vlanreq vlr

        memset(&vlr, 0, cython.sizeof(ifr))
        strcpy(ifr.ifr_name, self.name)
        strcpy(vlr.vlr_parent, '\0')
        vlr.vlr_tag = 0
        ifr.ifr_ifru.ifru_data = <defs.caddr_t>&vlr

        if self.ioctl(defs.SIOCSETVLAN, <void*>&ifr) == -1:
            raise OSError(errno, strerror(errno))

    property parent:
        def __get__(self):
            cdef defs.vlanreq vlr
            memset(&vlr, 0, cython.sizeof(vlr))

    property tag:
        def __get__(self):
            cdef defs.vlanreq vlr
            memset(&vlr, 0, cython.sizeof(vlr))


cdef class RoutingPacket(object):
    cdef readonly object data
    cdef char *buffer
    cdef size_t bufsize
    cdef defs.rt_msghdr *rt_msg

    def __init__(self, data=None):
        if data:
            self.data = data
            self.bufsize = len(data)
            self.buffer = <char*>data

        self.rt_msg = <defs.rt_msghdr*>self.buffer

    def __getstate__(self):
        return {
            'type': self.type.name,
            'version': self.version,
            'length': self.length
        }

    cdef _grow(self, amount):
        self.bufsize += amount
        self.buffer = <char*>realloc(self.buffer, self.bufsize)
        self.rt_msg = <defs.rt_msghdr*>self.buffer

    cdef _align_sa_len(self, int length):
        return 1 + ((length - 1) | (cython.sizeof(long) - 1))

    cdef _parse_sockaddr_dl(self, defs.sockaddr_dl* sdl):
        cdef char ifname[defs.IFNAMSIZ]

        result = LinkAddress(sdl.sdl_data[:sdl.sdl_nlen])
        if not result.ifname:
            defs.if_indextoname(sdl.sdl_index, ifname)
            result.ifname = ifname

        result.address = ':'.join(['{0:02x}'.format(ord(x)) for x in sdl.sdl_data[sdl.sdl_nlen:sdl.sdl_nlen+sdl.sdl_alen]])
        return result

    cdef _parse_sockaddrs(self, int start_offset, int mask):
        cdef defs.sockaddr* sa
        cdef defs.sockaddr_in* sin
        cdef defs.sockaddr_in6* sin6
        cdef char netmask[16]

        addr_sa_family = None
        ptr = start_offset
        result = {}

        for i in range(0, 7):
            if not mask & (1 << i):
                continue

            sa = <defs.sockaddr*>&self.buffer[ptr]
            ptr += self._align_sa_len(sa.sa_len)

            if sa.sa_family == defs.AF_INET:
                addr_sa_family = sa.sa_family
                sin = <defs.sockaddr_in*>sa
                result[i] = ipaddress.ip_address(socket.ntohl(sin.sin_addr.s_addr))

            elif sa.sa_family == defs.AF_INET6:
                addr_sa_family = sa.sa_family
                sin6 = <defs.sockaddr_in6*>sa
                result[i] = ipaddress.ip_address(sin6.sin6_addr.s6_addr[:16])

            elif sa.sa_family == defs.AF_LINK:
                sdl = <defs.sockaddr_dl*>sa
                result[i] = self._parse_sockaddr_dl(sdl)

            elif sa.sa_family in (0x00, 0xff) and i == defs.RTAX_NETMASK:
                # Hack for getting netmask information when parsing route messages
                # obtained via sysctl(3). I don't know why netmask sockaddrs are malformed.
                if addr_sa_family == defs.AF_INET:
                    result[i] = ipaddress.ip_address(sa.sa_data[2:6])

                if addr_sa_family == defs.AF_INET6:
                    sin6 = <defs.sockaddr_in6*>sa
                    memset(netmask, 0, sizeof(mask))
                    memcpy(netmask, &sin6.sin6_addr, min(16, sa.sa_len - 8))
                    result[i] = ipaddress.ip_address(netmask[:16])

        return result

    cdef _pack_sockaddrs(self, int start_offset, addrs):
        cdef defs.sockaddr_dl* sdl
        cdef defs.sockaddr_in* sin
        cdef defs.sockaddr_in6* sin6
        cdef int ptr
        cdef int mask

        mask = 0
        ptr = start_offset

        for rtax, i in addrs.items():
            if not i:
                continue

            mask |= (1 << rtax)

            if type(i) is LinkAddress:
                sa_size = self._align_sa_len(sizeof(defs.sockaddr_dl))
                print 'sa_size={0}'.format(sa_size)
                self._grow(sa_size)
                sdl = <defs.sockaddr_dl*>&self.buffer[ptr]
                memset(sdl, 0, sa_size)
                sdl.sdl_family = defs.AF_LINK
                sdl.sdl_len = cython.sizeof(defs.sockaddr_dl)
                sdl.sdl_index = defs.if_nametoindex(i.ifname)
                ptr += sa_size

            elif i.version == 4:
                sa_size = self._align_sa_len(sizeof(defs.sockaddr_in))
                print 'sa_size={0}'.format(sa_size)
                self._grow(sa_size)
                sin = <defs.sockaddr_in*>&self.buffer[ptr]
                memset(sin, 0, sa_size)
                sin.sin_family = defs.AF_INET
                sin.sin_len = cython.sizeof(defs.sockaddr_in)
                sin.sin_addr.s_addr = socket.htonl(int(i))
                ptr += sa_size

            elif i.version == 6:
                sa_size = self._align_sa_len(sizeof(defs.sockaddr_in6))
                print 'sa_size={0}'.format(sa_size)
                self._grow(sa_size)
                sin6 = <defs.sockaddr_in6*>&self.buffer[ptr]
                memset(sin6, 0, sa_size)
                sin6.sin6_family = defs.AF_INET6
                sin6.sin6_len = cython.sizeof(defs.sockaddr_in6)
                ptr += sa_size

        return mask

    property type:
        def __get__(self):
            return RoutingMessageType(self.rt_msg.rtm_type)

        def __set__(self, value):
            self.rt_msg.rtm_type = value

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
            'interface': self.interface,
            'type': self.type
        })

        return state

    property interface:
        def __get__(self):
            return self.header.ifan_name

    property type:
        def __get__(self):
            return InterfaceAnnounceType(self.header.ifan_what)


cdef class InterfaceInfoMessage(RoutingPacket):
    cdef defs.if_msghdr *header
    cdef readonly object addrs
    cdef int addrs_mask

    def __init__(self, packet):
        super(InterfaceInfoMessage, self).__init__(packet)
        self.header = <defs.if_msghdr*>self.buffer
        self.addrs_mask = self.header.ifm_addrs
        self.addrs = self._parse_sockaddrs(cython.sizeof(defs.if_msghdr), self.addrs_mask)

    def __getstate__(self):
        state = super(InterfaceInfoMessage, self).__getstate__()
        state.update({
            'flags': self.flags,
            'interface': self.interface,
            'link-state': self.link_state
        })

        return state

    property flags:
        def __get__(self):
            return bitmask_to_set(self.header.ifm_flags, InterfaceFlags)

    property link_state:
        def __get__(self):
            return InterfaceLinkState(self.header.ifm_data.ifi_link_state)

    property mtu:
        def __get__(self):
            return self.header.ifm_data.ifi_mtu

    property interface:
        def __get__(self):
            cdef char ifname[defs.IFNAMSIZ]
            defs.if_indextoname(self.header.ifm_index, ifname)
            return ifname

cdef class InterfaceAddrMessage(RoutingPacket):
    cdef defs.ifa_msghdr *header
    cdef readonly object addrs
    cdef int addrs_mask

    def __init__(self, packet):
        super(InterfaceAddrMessage, self).__init__(packet)
        self.header = <defs.ifa_msghdr*>self.buffer
        self.addrs_mask = self.header.ifam_addrs
        self.addrs = self._parse_sockaddrs(cython.sizeof(defs.ifa_msghdr), self.addrs_mask)

    def __getstate__(self):
        state = super(InterfaceAddrMessage, self).__getstate__()
        state.update({
            'flags': self.flags,
            'interface': self.interface,
        })

        if self.address:
            state['address'] = str(self.address)

        if self.netmask:
            state['netmask'] = str(self.netmask)

        if self.dest_address:
            state['dest-address'] = str(self.dest_address)

        return state

    property address:
        def __get__(self):
            if defs.RTAX_IFA in self.addrs:
                return self.addrs[defs.RTAX_IFA]

            return None

    property netmask:
        def __get__(self):
            if defs.RTAX_NETMASK in self.addrs:
                return self.addrs[defs.RTAX_NETMASK]

            return None

    property dest_address:
        def __get__(self):
            if defs.RTAX_BRD in self.addrs:
                return self.addrs[defs.RTAX_BRD]

            return None

    property flags:
        def __get__(self):
            return bitmask_to_set(self.header.ifam_flags, InterfaceFlags)

    property interface:
        def __get__(self):
            cdef char ifname[defs.IFNAMSIZ]
            defs.if_indextoname(self.header.ifam_index, ifname)
            return ifname


cdef class RoutingMessage(RoutingPacket):
    cdef readonly object addrs
    cdef int addrs_mask

    def __init__(self, packet=None):
        if not packet:
            self.bufsize = cython.sizeof(defs.rt_msghdr)
            self.buffer = <char*>malloc(self.bufsize)
            memset(self.buffer, 0, self.bufsize)

        super(RoutingMessage, self).__init__(packet)
        self.addrs_mask = self.rt_msg.rtm_addrs
        self.addrs = self._parse_sockaddrs(cython.sizeof(defs.rt_msghdr), self.addrs_mask)

    def __getstate__(self):
        state = super(RoutingMessage, self).__getstate__()
        gateway = None
        if self.gateway is not None:
            gateway = self.gateway.__getstate__() if type(self.gateway) is LinkAddress else str(self.gateway)

        state.update({
            'errno': self.errno,
            'flags': [x.name for x in self.flags],
            'interface': self.interface,
            'network': str(self.network),
            'gateway': gateway
        })

        if self.netmask:
            state['netmask'] = str(self.netmask)

        return state

    def as_buffer(self):
        self.rt_msg.rtm_version = 5
        self.rt_msg.rtm_addrs = self._pack_sockaddrs(cython.sizeof(defs.rt_msghdr), self.addrs)
        self.rt_msg.rtm_msglen = self.bufsize
        return self.buffer[:self.bufsize]

    property errno:
        def __get__(self):
            return self.rt_msg.rtm_errno

    property flags:
        def __get__(self):
            return bitmask_to_set(self.rt_msg.rtm_flags, RouteFlags)

        def __set__(self, value):
            self.rt_msg.rtm_flags = set_to_bitmask(value)

    property interface:
        def __get__(self):
            cdef char ifname[defs.IFNAMSIZ]
            cdef char* result
            result = defs.if_indextoname(self.rt_msg.rtm_index, ifname)
            return result if result != NULL else None

        def __set__(self, value):
            self.rt_msg.rtm_index = defs.if_nametoindex(value)

    property network:
        def __get__(self):
            if defs.RTAX_DST in self.addrs:
                return self.addrs[defs.RTAX_DST]

            return None

        def __set__(self, value):
            self.addrs[defs.RTAX_DST] = value

    property netmask:
        def __get__(self):
            if defs.RTAX_NETMASK in self.addrs:
                return self.addrs[defs.RTAX_NETMASK]

            return None

        def __set__(self, value):
            self.addrs[defs.RTAX_NETMASK] = value

    property gateway:
        def __get__(self):
            if defs.RTAX_GATEWAY in self.addrs:
                return self.addrs[defs.RTAX_GATEWAY]

            return None

        def __set__(self, value):
            self.addrs[defs.RTAX_GATEWAY] = value

    property route:
        def __get__(self):
            result = Route(
                self.network,
                self.netmask,
                self.gateway,
                self.interface
            )

            result.flags = self.flags
            return result

        def __set__(self, route):
            self.network = route.network
            self.netmask = route.netmask
            self.gateway = route.gateway
            self.flags = route.flags & {RouteFlags.STATIC, RouteFlags.GATEWAY, RouteFlags.HOST}
            if route.interface:
                self.interface = route.interface


class Route(object):
    def __init__(self, network, netmask, gateway=None, interface=None):
        self.network = ipaddress.ip_address(network)
        self.netmask = None
        self.gateway = None
        self.interface = None
        self.flags = set()

        if netmask:
            self.netmask = ipaddress.ip_address(netmask)

        if gateway:
            if type(gateway) is LinkAddress:
                self.gateway = gateway.ifname
            else:
                self.gateway = ipaddress.ip_address(gateway)

        if interface:
            self.interface = interface

    @property
    def af(self):
        if not self.network:
            return None

        if self.network.version == 4:
            return AddressFamily.INET

        if self.network.version == 6:
            return AddressFamily.INET6

        return None

    def __getstate__(self):
        return {
            'network': str(self.network),
            'netmask': str(self.netmask) if self.netmask else None,
            'gateway': str(self.gateway) if self.gateway else None,
            'interface': self.interface or None,
            'flags': [x.name for x in self.flags]
        }

    def __eq__(self, other):
        return self.network == other.network and \
            self.netmask == other.netmask and \
            self.gateway == other.gateway

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((
            self.network,
            self.netmask,
            self.gateway
        ))


class RoutingTable(object):
    def __init__(self):
        pass

    def __send_message(self, msg):
        if msg.type == RoutingMessageType.DELETE:
            msg.gateway = None

        sock = RoutingSocket()
        sock.open()
        sock.write_message(msg)
        sock.close()

    def __send_route(self, type, route):
        msg = RoutingMessage()
        msg.type = type
        msg.route = route
        print msg.__getstate__()
        self.__send_message(msg)

    @property
    def default_route_ipv4(self):
        f = filter(lambda r: int(r.network) == 0 and r.af == AddressFamily.INET, self.routes)
        return f[0] if len(f) > 0 else None

    @property
    def default_route_ipv6(self):
        f = filter(lambda r: int(r.network) == 0 and r.af == AddressFamily.INET6, self.routes)
        return f[0] if len(f) > 0 else None

    @property
    def routes(self):
        cdef char* buf
        cdef defs.rt_msghdr* rt_msg

        data = sysctl.sysctl([defs.CTL_NET, defs.AF_ROUTE, 0, 0, defs.NET_RT_DUMP, 0])
        data = array.array('b', data).tostring()
        buf = data
        ptr = 0

        while ptr < len(data):
            rt_msg = <defs.rt_msghdr*>&buf[ptr]
            msg = RoutingMessage(data[ptr:ptr+rt_msg.rtm_msglen])
            ptr += rt_msg.rtm_msglen
            yield msg.route

    @property
    def default_route(self):
        f = filter(lambda r: r.network == ipaddress.ip_address(u'0.0.0.0'), self.routes)
        return f[0] if f else None

    @property
    def static_routes(self):
        return filter(lambda r: RouteFlags.STATIC in r.flags and r.network != ipaddress.ip_address(u'0.0.0.0'), self.routes)

    def add(self, route):
        self.__send_route(RoutingMessageType.ADD, route)

    def delete(self, route):
        self.__send_route(RoutingMessageType.DELETE, route)

    def change(self, route):
        self.__send_route(RoutingMessageType.CHANGE, route)


class RoutingSocket(object):
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

        if packet is None:
            return None

        buffer = <char*>packet
        rt_msg = <defs.rt_msghdr*>buffer

        if rt_msg.rtm_type in (RoutingMessageType.IFANNOUNCE, RoutingMessageType.IEEE80211):
            return InterfaceAnnounceMessage(packet)

        if rt_msg.rtm_type == RoutingMessageType.IFINFO:
            return InterfaceInfoMessage(packet)

        if rt_msg.rtm_type in (RoutingMessageType.NEWADDR, RoutingMessageType.DELADDR):
            return InterfaceAddrMessage(packet)

        return RoutingMessage(packet)

    def write_message(self, message):
        buf = message.as_buffer()
        print repr(buf)
        os.write(self.socket.fileno(), buf)


def list_interfaces(iname=None):
    cdef defs.ifaddrs* ifa
    cdef defs.ifaddrs* orig
    cdef defs.sockaddr_in* sin
    cdef defs.sockaddr_in6* sin6
    cdef defs.sockaddr_dl* sdl
    cdef defs.sockaddr* sa

    if defs.getifaddrs(&ifa) != 0:
        return None

    orig = ifa
    result = {}

    while ifa:
        name = ifa.ifa_name

        if name not in result:
            if name.startswith('vlan'):
                result[name] = VlanInterface(name)
            else:
                result[name] = NetworkInterface(name)

        nic = result[name]
        sa = ifa.ifa_addr
        addr = InterfaceAddress(AddressFamily(sa.sa_family))

        if sa.sa_family == defs.AF_INET:
            if ifa.ifa_addr != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_addr
                addr.address = ipaddress.ip_address(socket.ntohl(sin.sin_addr.s_addr))

            if ifa.ifa_netmask != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_netmask
                addr.netmask = ipaddress.ip_address(socket.ntohl(sin.sin_addr.s_addr))

            if ifa.ifa_broadaddr != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_broadaddr
                addr.broadcast = ipaddress.ip_address(socket.ntohl(sin.sin_addr.s_addr))

            elif ifa.ifa_dstaddr != NULL:
                sin = <defs.sockaddr_in*>ifa.ifa_dstaddr
                addr.dest_address = ipaddress.ip_address(socket.ntohl(sin.sin_addr.s_addr))

        if sa.sa_family == defs.AF_INET6:
            if ifa.ifa_addr != NULL:
                sin6 = <defs.sockaddr_in6*>ifa.ifa_addr
                addr.address = ipaddress.ip_address(sin6.sin6_addr.s6_addr[:16])
                if str(addr.address).startswith('fe80:'):
                    addr.scope = sin6.sin6_scope_id

            if ifa.ifa_netmask != NULL:
                sin6 = <defs.sockaddr_in6*>ifa.ifa_addr
                addr.netmask = ipaddress.ip_address(sin6.sin6_addr.s6_addr[:16])

        if sa.sa_family == defs.AF_LINK:
            if ifa.ifa_addr != NULL:
                sdl = <defs.sockaddr_dl*>ifa.ifa_addr
                nic.type = InterfaceType(sdl.sdl_type)
                addr.address = LinkAddress(
                    sdl.sdl_data[:sdl.sdl_nlen],
                    ':'.join(['{0:02x}'.format(ord(x)) for x in sdl.sdl_data[sdl.sdl_nlen:sdl.sdl_nlen+sdl.sdl_alen]]))

        nic.addresses.append(addr)

        if ifa.ifa_next:
            ifa = ifa.ifa_next
        else:
            break

    defs.freeifaddrs(orig)
    if iname:
        return result[iname]
    return result


def bitmask_to_set(n, enumeration):
    result = set()
    while n:
        b = n & (~n+1)
        try:
            result.add(enumeration(b))
        except ValueError:
            pass

        n ^= b

    return result


def set_to_bitmask(value):
    result = 0
    for i in value:
        result |= int(i)

    return result


def get_interface(name):
    return list_interfaces(name)


def create_interface(name):
    cdef defs.ifreq ifr
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    strcpy(ifr.ifr_name, name)
    if defs.ioctl(s.fileno(), defs.SIOCIFCREATE, <void*>&ifr) == -1:
        raise OSError(errno, strerror(errno))

    s.close()
    return ifr.ifr_name


def destroy_interface(name):
    cdef defs.ifreq ifr
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    strcpy(ifr.ifr_name, name)
    if defs.ioctl(s.fileno(), defs.SIOCIFDESTROY, <void*>&ifr) == -1:
        raise OSError(errno, strerror(errno))

    s.close()
    return ifr.ifr_name
