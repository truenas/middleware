from dataclasses import dataclass
from socket import AF_INET, AF_INET6, AF_UNIX, SO_PEERCRED, SOL_SOCKET
from struct import calcsize, unpack

from pyroute2 import DiagSocket

__all__ = ('ConnectionOrigin',)

HA_HEARTBEAT_IPS = ('169.254.10.1', '169.254.10.2')
UIDS_TO_CHECK = (33, 0)


@dataclass(slots=True, frozen=True, kw_only=True)
class ConnectionOrigin:
    family: AF_INET | AF_INET6 | AF_UNIX
    """The address family associated to the API connection"""
    loc_addr: str | None = None
    """If `family` is not of type AF_UNIX, this represents
    the local IP address associated to the TCP/IP connection"""
    loc_port: int | None = None
    """If `family` is not of type AF_UNIX, this represents
    the local port associated to the TCP/IP connection"""
    rem_addr: str | None = None
    """If `family` is not of type AF_UNIX, this represents
    the remote IP address associated to the TCP/IP connection"""
    rem_port: int | None = None
    """If `family` is not of type AF_UNIX, this represents
    the remote port associated to the TCP/IP connection"""
    pid: int | None = None
    """If `family` is of type AF_UNIX, this represents
    the process id associated to the unix datagram connection"""
    uid: int | None = None
    """If `family` is of type AF_UNIX, this represents
    the user id associated to the unix datagram connection"""
    gid: int | None = None
    """If `family` is of type AF_UNIX, this represents
    the group id associated to the unix datagram connection"""

    @classmethod
    def create(cls, request):
        try:
            sock = request.transport.get_extra_info("socket")
            if sock.family == AF_UNIX:
                pid, uid, gid = unpack("3i", sock.getsockopt(SOL_SOCKET, SO_PEERCRED, calcsize("3i")))
                return cls(
                    family=sock.family,
                    pid=pid,
                    uid=uid,
                    gid=gid
                )
            elif sock.family in (AF_INET, AF_INET6):
                la, lp, ra, rp = get_tcp_ip_info(sock, request)
                return cls(
                    family=sock.family,
                    loc_addr=la,
                    loc_port=lp,
                    rem_addr=ra,
                    rem_port=rp,
                )
        except AttributeError:
            # request.transport can be None by the time this is
            # called on HA systems because remote node could
            # have been rebooted
            return

    def __str__(self) -> str:
        if self.is_unix_family:
            return f"UNIX socket (pid={self.pid} uid={self.uid} gid={self.gid})"
        elif self.family == AF_INET:
            return f"{self.rem_addr}:{self.rem_port}"
        elif self.family == AF_INET6:
            return f"[{self.rem_addr}]:{self.rem_port}"

    def match(self, origin) -> bool:
        if self.is_unix_family:
            return self.uid == origin.uid and self.gid == origin.gid
        else:
            return self.rem_addr == origin.rem_addr

    @property
    def repr(self) -> str:
        return f"pid:{self.pid}" if self.is_unix_family else self.rem_addr

    @property
    def is_tcp_ip_family(self) -> bool:
        return self.family in (AF_INET, AF_INET6)

    @property
    def is_unix_family(self) -> bool:
        return self.family == AF_UNIX

    @property
    def is_ha_connection(self) -> bool:
        return (
            self.family in (AF_INET, AF_INET6) and
            self.rem_port and self.rem_port <= 1024 and
            self.rem_addr and self.rem_addr in HA_HEARTBEAT_IPS
        )


def get_tcp_ip_info(sock, request) -> tuple:
    # All API connections are terminated by nginx reverse
    # proxy so the remote address is always 127.0.0.1. The
    # only exceptions to this are:
    #   1. Someone connects directly to 127.0.0.1 via a local
    #       shell session
    #   2. Someone connects directly to heartbeat IP port 6000
    #       via a local shell session on a TrueNAS HA system
    #   3. We connect directly to the other controller on an HA
    #       machine via heartbeat IP for intra-node communication.
    #       (this is done by us)
    try:
        # These headers are set by nginx or a user trying to do
        # (potentially) nefarious things. If these are set then
        # we need to check if the UID of the socket is owned by
        # 0 (root) or 33 (www-data (nginx forks workers))
        ra = request.headers["X-Real-Remote-Addr"]
        rp = int(request.headers["X-Real-Remote-Port"])
        check_uids = True
    except (KeyError, ValueError):
        ra, rp = sock.getpeername()
        check_uids = False

    with DiagSocket() as ds:
        ds.bind()
        for i in ds.get_sock_stats(family=sock.family):
            if i['idiag_dst'] == ra and i['idiag_dport'] == rp:
                if check_uids:
                    if i['idiag_uid'] in UIDS_TO_CHECK:
                        return i['idiag_src'], i['idiag_sport'], i['idiag_dst'], i['idiag_dport']
                else:
                    return i['idiag_src'], i['idiag_sport'], i['idiag_dst'], i['idiag_dport']
    return (None, None, None, None)
