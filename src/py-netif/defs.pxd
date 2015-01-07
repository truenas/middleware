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
        AF_INET
        AF_INET6
        AF_LINK
        AF_ROUTE

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
    cdef union ifreq_ifru:
        sockaddr ifru_addr
        sockaddr ifru_dstaddr
        sockaddr ifru_broadaddr
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
        u_char ifi_type
        u_char ifi_physical
        u_char ifi_addrlen
        u_char ifi_hdrlen
        u_char ifi_link_state
        u_char ifi_vhid
        u_char ifi_baudrate_pf
        u_char ifi_datalen
        u_long ifi_mtu
        u_long ifi_metric
        u_long ifi_baudrate
        u_long ifi_ipackets
        u_long ifi_ierrors
        u_long ifi_opackets
        u_long ifi_oerrors
        u_long ifi_collisions
        u_long ifi_ibytes
        u_long ifi_obytes
        u_long ifi_imcasts
        u_long ifi_omcasts
        u_long ifi_iqdrops
        u_long ifi_noproto
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