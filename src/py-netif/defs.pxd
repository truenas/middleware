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


from libc.stdint cimport *
from posix.types cimport *


cdef extern from "net/if.h":
    enum:
        IFNAMSIZ


cdef extern from "sys/sysctl.h":
    enum:
        CTL_UNSPEC
        CTL_KERN
        CTL_VM
        CTL_VFS
        CTL_NET
        CTL_DEBUG
        CTL_HW
        CTL_MACHDEP
        CTL_USER
        CTL_P1003_1B

cdef extern from "sys/types.h":
    ctypedef unsigned char u_char
    ctypedef unsigned short u_short
    ctypedef unsigned long u_long
    ctypedef long caddr_t
    ctypedef char sa_family_t
    ctypedef short in_port_t
    ctypedef int in_addr


cdef extern from "ifaddrs.h":
    cdef struct ifaddrs:
        ifaddrs* ifa_next
        char* ifa_name
        unsigned int ifa_flags
        sockaddr* ifa_addr
        sockaddr* ifa_netmask
        sockaddr* ifa_broadaddr
        sockaddr* ifa_dstaddr
        void* ifa_data

    cdef int getifaddrs(ifaddrs** ifap)
    cdef void freeifaddrs(ifaddrs* ifp)


cdef extern from "sys/socket.h":
    cdef struct sockaddr:
        unsigned char sa_len
        sa_family_t sa_family
        char sa_data[14]

    enum:
        AF_UNIX
        AF_INET
        AF_IMPLINK
        AF_PUP
        AF_CHAOS
        AF_NETBIOS
        AF_ISO
        AF_OSI
        AF_ECMA
        AF_DATAKIT
        AF_CCITT
        AF_SNA
        AF_DECnet
        AF_DLI
        AF_LAT
        AF_HYLINK
        AF_APPLETALK
        AF_ROUTE
        AF_LINK
        AF_COIP
        AF_CNT
        AF_IPX
        AF_SIP
        AF_ISDN
        AF_E164
        AF_INET6
        AF_NATM
        AF_ATM
        AF_NETGRAPH
        AF_SLOW
        AF_SCLUSTER
        AF_ARP
        AF_BLUETOOTH
        AF_IEEE80211
        AF_INET_SDP
        AF_INET6_SDP

    enum:
        NET_RT_DUMP
        NET_RT_FLAGS
        NET_RT_IFLIST
        NET_RT_IFMALIST
        NET_RT_IFLISTL


cdef extern from "netinet/in.h":
    ctypedef struct in_addr_t:
        uint32_t s_addr

    cdef struct sockaddr_in:
        uint8_t sin_len
        sa_family_t sin_family
        in_port_t sin_port
        in_addr_t sin_addr
        char sin_zero[8]

    cdef struct in6_addr:
        uint8_t s6_addr[16]

    cdef struct sockaddr_in6:
        uint8_t sin6_len
        sa_family_t sin6_family
        in_port_t sin6_port
        uint32_t sin6_flowinfo
        in6_addr sin6_addr
        uint32_t sin6_scope_id


cdef extern from "net/if_dl.h":
    cdef struct sockaddr_dl:
        u_char sdl_len
        u_char sdl_family
        u_short sdl_index
        u_char sdl_type
        u_char sdl_nlen
        u_char sdl_alen
        u_char sdl_slen
        char sdl_data[46]


cdef extern from "net/if.h":
    enum:
        LINK_STATE_UNKNOWN
        LINK_STATE_DOWN
        LINK_STATE_UP

    enum:
        IFAN_ARRIVAL
        IFAN_DEPARTURE

    cdef struct ifreq_buffer:
        size_t length
        void* buffer

    cdef union ifreq_ifru:
        sockaddr ifru_addr
        sockaddr ifru_dstaddr
        sockaddr ifru_broadaddr
        ifreq_buffer ifru_buffer
        short ifru_flags[2]
        short ifru_index
        int ifru_metric
        int ifru_mtu
        int ifru_phys
        int  ifru_media
        caddr_t  ifru_data
        int ifru_cap[2]

    cdef struct ifreq:
        char ifr_name[IFNAMSIZ]
        ifreq_ifru ifr_ifru

    cdef struct ifaliasreq:
        char ifra_name[IFNAMSIZ]
        sockaddr ifra_addr
        sockaddr ifra_broadaddr
        sockaddr ifra_mask
        int ifra_vhid

    cdef struct if_data:
        uint8_t ifi_type
        uint8_t ifi_physical
        uint8_t ifi_addrlen
        uint8_t ifi_hdrlen
        uint8_t ifi_link_state
        uint8_t ifi_vhid
        uint8_t ifi_baudrate_pf
        uint16_t ifi_datalen
        uint32_t ifi_mtu
        uint32_t ifi_metric
        uint64_t ifi_baudrate
        uint64_t ifi_ipackets
        uint64_t ifi_ierrors
        uint64_t ifi_opackets
        uint64_t ifi_oerrors
        uint64_t ifi_collisions
        uint64_t ifi_ibytes
        uint64_t ifi_obytes
        uint64_t ifi_imcasts
        uint64_t ifi_omcasts
        uint64_t ifi_iqdrops
        uint64_t ifi_noproto
        uint64_t ifi_hwassist
        time_t ifi_epoch

    cdef struct if_msghdr:
        u_short ifm_msglen
        u_char ifm_version
        u_char ifm_type
        int ifm_addrs
        int ifm_flags
        u_short ifm_index
        if_data ifm_data

    cdef struct ifa_msghdr:
        u_short ifam_msglen
        u_char ifam_version
        u_char ifam_type
        int ifam_addrs
        int ifam_flags
        u_short ifam_index
        int ifam_metric

    cdef struct if_announcemsghdr:
        u_short ifan_msglen
        u_char ifan_version
        u_char ifan_type
        u_short ifan_index
        char ifan_name[IFNAMSIZ]
        u_short ifan_what

    unsigned int if_nametoindex(const char* name)
    char* if_indextoname(unsigned int ifindex, char *ifname)

#cdef extern from "netinet6/in6_var.h":
#    cdef union in6_ifreq_ifru:
#        int a

#    cdef struct in6_ifreq:
#        char ifr_name[IFNAMSIZ]
#        in6_ifreq_ifru ifr_ifru


cdef extern from "net/if_media.h":
    cdef struct ifmediareq:
        char ifm_name[IFNAMSIZ]
        int ifm_current
        int ifm_mask
        int ifm_status
        int ifm_active
        int ifm_count
        int *ifm_ulist


cdef extern from "net/route.h":
    enum:
        RTM_ADD
        RTM_DELETE
        RTM_CHANGE
        RTM_GET
        RTM_LOSING
        RTM_REDIRECT
        RTM_MISS
        RTM_LOCK
        RTM_RESOLVE
        RTM_NEWADDR
        RTM_DELADDR
        RTM_IFINFO
        RTM_NEWMADDR
        RTM_DELMADDR
        RTM_IFANNOUNCE
        RTM_IEEE80211

    enum:
        RTF_UP
        RTF_GATEWAY
        RTF_HOST
        RTF_REJECT
        RTF_DYNAMIC
        RTF_MODIFIED
        RTF_DONE
        RTF_XRESOLVE
        RTF_LLINFO
        RTF_LLDATA
        RTF_STATIC
        RTF_BLACKHOLE
        RTF_PROTO1
        RTF_PROTO2
        RTF_PROTO3
        RTF_PINNED
        RTF_LOCAL
        RTF_BROADCAST
        RTF_MULTICAST
        RTF_STICKY

    enum:
        RTA_DST
        RTA_GATEWAY
        RTA_NETMASK
        RTA_GENMASK
        RTA_IFP
        RTA_IFA
        RTA_AUTHOR
        RTA_BRD

    enum:
        RTAX_DST
        RTAX_GATEWAY
        RTAX_NETMASK
        RTAX_GENMASK
        RTAX_IFP
        RTAX_IFA
        RTAX_AUTHOR
        RTAX_BRD
        RTAX_MAX

    cdef struct rt_metrics:
        u_long rmx_locks
        u_long rmx_mtu
        u_long rmx_hopcount
        u_long rmx_expire
        u_long rmx_recvpipe
        u_long rmx_sendpipe
        u_long rmx_ssthresh
        u_long rmx_rtt
        u_long rmx_rttvar
        u_long rmx_pksent
        u_long rmx_weight
        u_long rmx_filler[3]

    cdef struct rt_msghdr:
        u_short rtm_msglen
        u_char rtm_version
        u_char rtm_type
        u_short rtm_index
        int rtm_flags
        int rtm_addrs
        pid_t rtm_pid
        int rtm_seq
        int rtm_errno
        int rtm_fmask
        u_long rtm_inits
        rt_metrics rtm_rmx


cdef extern from "sys/ioctl.h":
    cdef int ioctl(int fd, unsigned long request, ...)


cdef extern from "net/ethernet.h":
    enum:
        ETHER_ADDR_LEN


cdef extern from "sys/sockio.h":
    enum:
        SIOCSIFADDR
        SIOCGIFADDR
        SIOCSIFDSTADDR
        SIOCGIFDSTADDR
        SIOCSIFFLAGS
        SIOCGIFFLAGS
        SIOCGIFBRDADDR
        SIOCSIFBRDADDR
        SIOCGIFNETMASK
        SIOCSIFNETMASK
        SIOCGIFMETRIC
        SIOCSIFMETRIC
        SIOCDIFADDR
        SIOCSIFCAP
        SIOCGIFCAP
        SIOCGIFINDEX
        SIOCGIFMAC
        SIOCSIFMAC
        SIOCSIFNAME
        SIOCSIFDESCR
        SIOCGIFDESCR
        SIOCAIFADDR
        SIOCADDMULTI
        SIOCDELMULTI
        SIOCGIFMTU
        SIOCSIFMTU
        SIOCGIFPHYS
        SIOCSIFPHYS
        SIOCSIFMEDIA
        SIOCGIFMEDIA
        SIOCSIFGENERIC
        SIOCGIFGENERIC
        SIOCGIFSTATUS
        SIOCSIFLLADDR
        SIOCSIFPHYADDR
        SIOCGIFPSRCADDR
        SIOCGIFPDSTADDR
        SIOCDIFPHYADDR
        SIOCGPRIVATE_0
        SIOCGPRIVATE_1
        SIOCSIFVNET
        SIOCSIFRVNET
        SIOCGIFFIB
        SIOCSIFFIB
        SIOCSDRVSPEC
        SIOCGDRVSPEC
        SIOCIFCREATE
        SIOCIFCREATE2
        SIOCIFDESTROY
        SIOCIFGCLONERS
        SIOCAIFGROUP
        SIOCGIFGROUP
        SIOCDIFGROUP
        SIOCGIFGMEMB


cdef extern from "net/if_lagg.h":
    enum:
        SIOCGLAGGPORT
        SIOCSLAGGPORT
        SIOCSLAGGDELPORT
        SIOCGLAGG
        SIOCSLAGG
        SIOCGLAGGFLAGS
        SIOCSLAGGHASH


cdef extern from "net/if.h":
    enum:
        IFF_UP
        IFF_BROADCAST
        IFF_DEBUG
        IFF_LOOPBACK
        IFF_POINTOPOINT
        IFF_DRV_RUNNING
        IFF_NOARP
        IFF_PROMISC
        IFF_ALLMULTI
        IFF_DRV_OACTIVE
        IFF_SIMPLEX
        IFF_LINK0
        IFF_LINK1
        IFF_LINK2
        IFF_MULTICAST
        IFF_CANTCONFIG
        IFF_PPROMISC
        IFF_MONITOR
        IFF_STATICARP
        IFF_DYING
        IFF_RENAMING


cdef extern from "net/if_media.h":
    enum:
        IFM_AVALID
        IFM_ACTIVE


cdef extern from "net/if_vlan_var.h":
    enum:
        SIOCSETVLAN
        SIOCGETVLAN

    cdef struct vlanreq:
        char vlr_parent[IFNAMSIZ]
        u_short vlr_tag


cdef extern from "net/if_lagg.h":
    ctypedef enum lagg_proto:
        LAGG_PROTO_NONE
        LAGG_PROTO_ROUNDROBIN
        LAGG_PROTO_FAILOVER
        LAGG_PROTO_LOADBALANCE
        LAGG_PROTO_LACP
        LAGG_PROTO_ETHERCHANNEL
        LAGG_PROTO_BROADCAST
        LAGG_PROTO_MAX

    cdef struct lacp_opreq:
        uint16_t actor_prio
        uint8_t actor_mac[ETHER_ADDR_LEN]
        uint16_t actor_key
        uint16_t actor_portprio
        uint16_t actor_portno
        uint8_t actor_state
        uint16_t partner_prio
        uint8_t partner_mac[ETHER_ADDR_LEN]
        uint16_t partner_key
        uint16_t partner_portprio
        uint16_t partner_portno
        uint8_t partner_state

    cdef struct lagg_reqport:
        char rp_ifname[IFNAMSIZ]
        char rp_portname[IFNAMSIZ]
        uint32_t rp_prio
        uint32_t rp_flags


        
cdef extern from "net/if_types.h":
    enum:
        IFT_OTHER
        IFT_1822
        IFT_HDH1822
        IFT_X25DDN
        IFT_X25
        IFT_ETHER
        IFT_ISO88023
        IFT_ISO88024
        IFT_ISO88025
        IFT_ISO88026
        IFT_STARLAN
        IFT_P10
        IFT_P80
        IFT_HY
        IFT_FDDI
        IFT_LAPB
        IFT_SDLC
        IFT_T1
        IFT_CEPT
        IFT_ISDNBASIC
        IFT_ISDNPRIMARY
        IFT_PTPSERIAL
        IFT_PPP
        IFT_LOOP
        IFT_EON
        IFT_XETHER
        IFT_NSIP
        IFT_SLIP
        IFT_ULTRA
        IFT_DS3
        IFT_SIP
        IFT_FRELAY
        IFT_RS232
        IFT_PARA
        IFT_ARCNET
        IFT_ARCNETPLUS
        IFT_ATM
        IFT_MIOX25
        IFT_SONET
        IFT_X25PLE
        IFT_ISO88022LLC
        IFT_LOCALTALK
        IFT_SMDSDXI
        IFT_FRELAYDCE
        IFT_V35
        IFT_HSSI
        IFT_HIPPI
        IFT_MODEM
        IFT_AAL5
        IFT_SONETPATH
        IFT_SONETVT
        IFT_SMDSICIP
        IFT_PROPVIRTUAL
        IFT_PROPMUX
        IFT_IEEE80212
        IFT_FIBRECHANNEL
        IFT_HIPPIINTERFACE
        IFT_FRAMERELAYINTERCONNECT
        IFT_AFLANE8023
        IFT_AFLANE8025
        IFT_CCTEMUL
        IFT_FASTETHER
        IFT_ISDN
        IFT_V11
        IFT_V36
        IFT_G703AT64K
        IFT_G703AT2MB
        IFT_QLLC
        IFT_FASTETHERFX
        IFT_CHANNEL
        IFT_IEEE80211
        IFT_IBM370PARCHAN
        IFT_ESCON
        IFT_DLSW
        IFT_ISDNS
        IFT_ISDNU
        IFT_LAPD
        IFT_IPSWITCH
        IFT_RSRB
        IFT_ATMLOGICAL
        IFT_DS0
        IFT_DS0BUNDLE
        IFT_BSC
        IFT_ASYNC
        IFT_CNR
        IFT_ISO88025DTR
        IFT_EPLRS
        IFT_ARAP
        IFT_PROPCNLS
        IFT_HOSTPAD
        IFT_TERMPAD
        IFT_FRAMERELAYMPI
        IFT_X213
        IFT_ADSL
        IFT_RADSL
        IFT_SDSL
        IFT_VDSL
        IFT_ISO88025CRFPINT
        IFT_MYRINET
        IFT_VOICEEM
        IFT_VOICEFXO
        IFT_VOICEFXS
        IFT_VOICEENCAP
        IFT_VOICEOVERIP
        IFT_ATMDXI
        IFT_ATMFUNI
        IFT_ATMIMA
        IFT_PPPMULTILINKBUNDLE
        IFT_IPOVERCDLC
        IFT_IPOVERCLAW
        IFT_STACKTOSTACK
        IFT_VIRTUALIPADDRESS
        IFT_MPC
        IFT_IPOVERATM
        IFT_ISO88025FIBER
        IFT_TDLC
        IFT_GIGABITETHERNET
        IFT_HDLC
        IFT_LAPF
        IFT_V37
        IFT_X25MLP
        IFT_X25HUNTGROUP
        IFT_TRANSPHDLC
        IFT_INTERLEAVE
        IFT_FAST
        IFT_IP
        IFT_DOCSCABLEMACLAYER
        IFT_DOCSCABLEDOWNSTREAM
        IFT_DOCSCABLEUPSTREAM
        IFT_A12MPPSWITCH
        IFT_TUNNEL
        IFT_COFFEE
        IFT_CES
        IFT_ATMSUBINTERFACE
        IFT_L2VLAN
        IFT_L3IPVLAN
        IFT_L3IPXVLAN
        IFT_DIGITALPOWERLINE
        IFT_MEDIAMAILOVERIP
        IFT_DTM
        IFT_DCN
        IFT_IPFORWARD
        IFT_MSDSL
        IFT_IEEE1394
        IFT_IFGSN
        IFT_DVBRCCMACLAYER
        IFT_DVBRCCDOWNSTREAM
        IFT_DVBRCCUPSTREAM
        IFT_ATMVIRTUAL
        IFT_MPLSTUNNEL
        IFT_SRP
        IFT_VOICEOVERATM
        IFT_VOICEOVERFRAMERELAY
        IFT_IDSL
        IFT_COMPOSITELINK
        IFT_SS7SIGLINK
        IFT_PROPWIRELESSP2P
        IFT_FRFORWARD
        IFT_RFC1483
        IFT_USB
        IFT_IEEE8023ADLAG
        IFT_BGPPOLICYACCOUNTING
        IFT_FRF16MFRBUNDLE
        IFT_H323GATEKEEPER
        IFT_H323PROXY
        IFT_MPLS
        IFT_MFSIGLINK
        IFT_HDSL2
        IFT_SHDSL
        IFT_DS1FDL
        IFT_POS
        IFT_DVBASILN
        IFT_DVBASIOUT
        IFT_PLC
        IFT_NFAS
        IFT_TR008
        IFT_GR303RDT
        IFT_GR303IDT
        IFT_ISUP
        IFT_PROPDOCSWIRELESSMACLAYER
        IFT_PROPDOCSWIRELESSDOWNSTREAM
        IFT_PROPDOCSWIRELESSUPSTREAM
        IFT_HIPERLAN2
        IFT_PROPBWAP2MP
        IFT_SONETOVERHEADCHANNEL
        IFT_DIGITALWRAPPEROVERHEADCHANNEL
        IFT_AAL2
        IFT_RADIOMAC
        IFT_ATMRADIO
        IFT_IMT
        IFT_MVL
        IFT_REACHDSL
        IFT_FRDLCIENDPT
        IFT_ATMVCIENDPT
        IFT_OPTICALCHANNEL
        IFT_OPTICALTRANSPORT
        IFT_INFINIBAND
        IFT_BRIDGE
        IFT_STF
        IFT_GIF
        IFT_PVC
        IFT_FAITH
        IFT_ENC
        IFT_PFLOG
        IFT_PFSYNC