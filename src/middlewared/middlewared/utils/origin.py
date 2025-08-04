import socket

from dataclasses import dataclass
from ipaddress import ip_address
from socket import AF_INET, AF_INET6, AF_UNIX, SO_PEERCRED, SOL_SOCKET
from struct import calcsize, unpack

from pyroute2 import DiagSocket

from .auth import get_login_uid, AUID_UNSET

__all__ = ('ConnectionOrigin', 'is_external_call')

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
    loginuid: int | None = None
    """If `family` is of type AF_UNIX, this represents
    the login uid associated to the unix datagram connection.
    The login uid can be used to determine whether the connection was
    created by an interactive shell session"""
    ssl: bool = False
    """Nginx reports that https was used for connection"""

    @classmethod
    def create(cls, request):
        try:
            sock = request.transport.get_extra_info("socket")
            if sock.family == AF_UNIX:
                pid, uid, gid = unpack("3i", sock.getsockopt(SOL_SOCKET, SO_PEERCRED, calcsize("3i")))
                login_uid = get_login_uid(pid)
                return cls(
                    family=sock.family,
                    pid=pid,
                    uid=uid,
                    loginuid=login_uid,
                    gid=gid,
                )
            elif sock.family in (AF_INET, AF_INET6):
                la, lp, ra, rp, ssl = get_tcp_ip_info(sock, request)

                return cls(
                    family=sock.family,
                    loc_addr=la,
                    loc_port=lp,
                    rem_addr=ra,
                    rem_port=rp,
                    ssl=ssl
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
    def session_is_interactive(self) -> bool:
        """ This is used to indicate whether session is internal
        for purposes of STIG checks. This property is only set for
        AF_UNIX connections and indicates whether its an interactive """
        if self.loginuid is None:
            # Not AF_UNIX connection. Always apply restrictions
            # for interactive sessions.
            return True

        # self.loginuid may be set to AUID_FAULTED if for some reason
        # we encountered a major issue in retrieving the loginuid.
        # Since this value is used to determine whether to allow
        # enhanced privileges in STIG mode we treat AUID_FAULTED
        # as being an interactive session with less privileges afforded
        # it.
        return self.loginuid != AUID_UNSET

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

    @property
    def secure_transport(self) -> bool:
        """Indicates whether we should treat the connection as having
        secure transport for purposes of invalidation of API keys.
        Secure in this case means AF_UNIX, loopback connection, or
        transport is encrypted."""

        if self.ssl or self.is_unix_family or self.is_ha_connection:
            return True

        if self.is_tcp_ip_family:
            try:
                return ip_address(self.rem_addr).is_loopback
            except Exception:
                pass

        # By default assume that transport is insecure
        return False

    def ppids(self) -> set[int]:
        if self.pid is None:
            return set()

        pid = self.pid
        ppids = set()
        while True:
            try:
                with open(f"/proc/{pid}/status") as f:
                    pid = None
                    for line in f:
                        if line.startswith("PPid:"):
                            try:
                                pid = int(line.split(":")[1].strip())
                            except ValueError:
                                pass

                            break
            except FileNotFoundError:
                break

            if pid is not None:
                if pid <= 1:
                    break

                ppids.add(pid)
            else:
                break

        return ppids


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
        family = socket.AF_INET6 if ":" in ra else socket.AF_INET
        ssl = request.headers.get("X-Https", "") == "on"
        check_uids = True
    except (KeyError, ValueError):
        ra, rp = sock.getpeername()
        family = sock.family
        ssl = False
        check_uids = False

    with DiagSocket() as ds:
        ds.bind()
        for i in ds.get_sock_stats(family=family):
            if i['idiag_dst'] == ra and i['idiag_dport'] == rp:
                if check_uids:
                    if i['idiag_uid'] in UIDS_TO_CHECK:
                        return i['idiag_src'], i['idiag_sport'], i['idiag_dst'], i['idiag_dport'], ssl
                else:
                    return i['idiag_src'], i['idiag_sport'], i['idiag_dst'], i['idiag_dport'], ssl

    return None, None, None, None, None


def is_external_call(app):
    """
    Determine if this is an external API call that should be tracked.
    External calls are those which the system is not generating internally i.e self.middleware.call().

    Note: We intentionally track midclt calls (Unix socket) as they can be
    initiated by users and we want to track their usage patterns (this only applies to midclt calls
    where user has logged in to a shell and not internal calls made by scripts).

    Returns True for external calls, False for internal calls.
    """
    if app is None or app.origin is None:
        # No origin info, assume internal
        return False

    origin = app.origin

    # HA connections between nodes are internal
    if origin.is_ha_connection:
        return False

    return origin.session_is_interactive
