import socket
import struct
from contextvars import ContextVar
from dataclasses import dataclass, field

from .constants import (
    NETLINK_ROUTE,
    SOL_NETLINK,
    AddressFamily,
    IFAAttr,
    IFLAAttr,
    IFOperState,
    NetlinkSockOpt,
    NLAttrFlags,
    NLMsgFlags,
    NLMsgType,
    RTEXTFilter,
    RTMType,
)
from middlewared.plugins.interface.netif_linux.exceptions import (
    DeviceNotFound,
    DumpInterrupted,
    NetlinkError,
    OperationNotSupported,
)

__all__ = (
    "AddressInfo",
    "AddressNetlink",
    "DeviceNotFound",
    "DumpInterrupted",
    "IFOperState",
    "LinkInfo",
    "NetlinkError",
    "OperationNotSupported",
    "close_address_netlink",
    "get_address_netlink",
)

_address_ctx: ContextVar["AddressNetlink | None"] = ContextVar(
    "address_netlink", default=None
)


@dataclass(slots=True, frozen=True, kw_only=True)
class AddressInfo:
    # Fields used for equality and hashing
    family: int
    prefixlen: int
    address: str
    broadcast: str | None = None
    # Fields below are informational only - not used for equality/hashing
    flags: int = field(default=0, compare=False, hash=False)
    scope: int = field(default=0, compare=False, hash=False)
    index: int = field(default=0, compare=False, hash=False)
    ifname: str | None = field(default=None, compare=False, hash=False)
    local: str | None = field(default=None, compare=False, hash=False)
    label: str | None = field(default=None, compare=False, hash=False)
    # Extended fields from IFA_PROTO and IFA_CACHEINFO
    proto: int | None = field(default=None, compare=False, hash=False)
    valid_lft: int | None = field(
        default=None, compare=False, hash=False
    )  # seconds, None=forever
    preferred_lft: int | None = field(
        default=None, compare=False, hash=False
    )  # seconds, None=forever

    def asdict(self, stats: bool = False) -> dict:
        """Convert to dict format compatible with InterfaceAddress.asdict()."""
        if self.family == AddressFamily.INET:
            af_name = "INET"
        elif self.family == AddressFamily.INET6:
            af_name = "INET6"
        else:
            af_name = "LINK"

        result = {
            "type": af_name,
            "address": self.address,
        }
        if self.prefixlen:
            result["netmask"] = self.prefixlen
        if self.broadcast:
            result["broadcast"] = self.broadcast
        return result


@dataclass(slots=True, frozen=True, kw_only=True)
class LinkInfo:
    # Core fields
    index: int
    flags: int
    mtu: int
    operstate: int
    address: str | None = None
    perm_address: str | None = None
    broadcast: str | None = None
    # Extended fields
    txqlen: int = 0
    min_mtu: int = 0
    max_mtu: int = 0
    carrier: bool = False
    carrier_changes: int = 0
    num_tx_queues: int = 1
    num_rx_queues: int = 1
    # Parent device info (for USB detection, etc.)
    parentbus: str | None = None
    parentdev: str | None = None
    # Alternate names
    altnames: tuple[str, ...] = ()


@dataclass(slots=True)
class AddressNetlink:
    _sock: socket.socket | None = field(default=None, init=False)
    _seq: int = field(default=0, init=False)
    _pid: int | None = field(default=None, init=False)

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *args):
        self.close()

    def _connect(self):
        self._sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self._sock.bind((0, 0))
        self._pid = self._sock.getsockname()[0]

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def _pack_nlattr(self, attr_type: int, data: bytes) -> bytes:
        nla_len = 4 + len(data)
        padded_len = (nla_len + 3) & ~3
        padding = padded_len - nla_len
        return struct.pack("HH", nla_len, attr_type) + data + b"\x00" * padding

    def _pack_nlattr_str(self, attr_type: int, s: str) -> bytes:
        return self._pack_nlattr(attr_type, s.encode() + b"\x00")

    def _pack_nlattr_u32(self, attr_type: int, val: int) -> bytes:
        return self._pack_nlattr(attr_type, struct.pack("I", val))

    def _pack_nlattr_nested(self, attr_type: int, attrs: bytes) -> bytes:
        return self._pack_nlattr(attr_type | NLAttrFlags.NESTED, attrs)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _pack_nlmsg(self, msg_type: int, flags: int, payload: bytes) -> bytes:
        seq = self._next_seq()
        nlmsg_len = 16 + len(payload)
        return struct.pack("IHHII", nlmsg_len, msg_type, flags, seq, 0) + payload

    def _recv_msgs(self) -> list[tuple[int, bytes]]:
        messages = []
        while True:
            data = self._sock.recv(65536)
            offset = 0
            done = False
            while offset < len(data):
                if offset + 16 > len(data):
                    break
                nlmsg_len, nlmsg_type, nlmsg_flags, nlmsg_seq, nlmsg_pid = (
                    struct.unpack_from("IHHII", data, offset)
                )
                if nlmsg_len < 16:
                    break
                if nlmsg_flags & NLMsgFlags.DUMP_INTR:
                    raise DumpInterrupted("Netlink dump was interrupted")
                if nlmsg_type == NLMsgType.ERROR:
                    if offset + 20 <= len(data):
                        error = struct.unpack_from("i", data, offset + 16)[0]
                        if error < 0:
                            error = -error
                            if error == 19:  # ENODEV
                                raise DeviceNotFound("No such device")
                            elif error == 95:  # EOPNOTSUPP
                                raise OperationNotSupported("Operation not supported")
                            raise NetlinkError(f"Netlink error: {error}")
                    done = True
                elif nlmsg_type == NLMsgType.DONE:
                    done = True
                else:
                    payload = data[offset + 16 : offset + nlmsg_len]
                    messages.append((nlmsg_type, payload))
                offset += (nlmsg_len + 3) & ~3
            if done:
                break
        return messages

    def _parse_attrs(self, data: bytes, offset: int = 0) -> dict[int, bytes]:
        attrs = {}
        while offset + 4 <= len(data):
            nla_len, nla_type = struct.unpack_from("HH", data, offset)
            if nla_len < 4:
                break
            nla_type_base = nla_type & 0x7FFF
            attr_data = data[offset + 4 : offset + nla_len]
            attrs[nla_type_base] = attr_data
            offset += (nla_len + 3) & ~3
        return attrs

    def _parse_nested_attrs(self, data: bytes) -> dict[int, bytes]:
        return self._parse_attrs(data, 0)

    def _parse_link_payload(self, payload: bytes) -> tuple[str, LinkInfo] | None:
        """Parse a NEWLINK payload into (ifname, LinkInfo). Returns None if invalid."""
        if len(payload) < 16:
            return None

        # Parse ifinfomsg header
        ifi_family, ifi_type, ifi_index, ifi_flags, ifi_change = struct.unpack_from(
            "BxHiII", payload, 0
        )
        # Parse attributes after ifinfomsg (16 bytes)
        attrs = self._parse_attrs(payload, 16)

        ifname = None
        if IFLAAttr.IFNAME in attrs:
            ifname = (
                attrs[IFLAAttr.IFNAME].rstrip(b"\x00").decode("utf-8", errors="replace")
            )
        if not ifname:
            return None

        # Core fields
        mtu = 0
        operstate = 0
        address = None
        perm_address = None
        broadcast = None

        if IFLAAttr.MTU in attrs:
            mtu = struct.unpack("I", attrs[IFLAAttr.MTU][:4])[0]
        if IFLAAttr.OPERSTATE in attrs:
            operstate = attrs[IFLAAttr.OPERSTATE][0]
        if IFLAAttr.ADDRESS in attrs:
            address = attrs[IFLAAttr.ADDRESS].hex(":")
        if IFLAAttr.PERM_ADDRESS in attrs:
            perm_address = attrs[IFLAAttr.PERM_ADDRESS].hex(":")
        if IFLAAttr.BROADCAST in attrs:
            broadcast = attrs[IFLAAttr.BROADCAST].hex(":")

        # Extended fields
        txqlen = 0
        min_mtu = 0
        max_mtu = 0
        carrier = False
        carrier_changes = 0
        num_tx_queues = 1
        num_rx_queues = 1

        if IFLAAttr.TXQLEN in attrs:
            txqlen = struct.unpack("I", attrs[IFLAAttr.TXQLEN][:4])[0]
        if IFLAAttr.MIN_MTU in attrs:
            min_mtu = struct.unpack("I", attrs[IFLAAttr.MIN_MTU][:4])[0]
        if IFLAAttr.MAX_MTU in attrs:
            max_mtu = struct.unpack("I", attrs[IFLAAttr.MAX_MTU][:4])[0]
        if IFLAAttr.CARRIER in attrs:
            carrier = attrs[IFLAAttr.CARRIER][0] != 0
        if IFLAAttr.CARRIER_CHANGES in attrs:
            carrier_changes = struct.unpack("I", attrs[IFLAAttr.CARRIER_CHANGES][:4])[0]
        if IFLAAttr.NUM_TX_QUEUES in attrs:
            num_tx_queues = struct.unpack("I", attrs[IFLAAttr.NUM_TX_QUEUES][:4])[0]
        if IFLAAttr.NUM_RX_QUEUES in attrs:
            num_rx_queues = struct.unpack("I", attrs[IFLAAttr.NUM_RX_QUEUES][:4])[0]

        # Parent device info (for USB detection, etc.)
        parentbus = None
        parentdev = None

        if IFLAAttr.PARENT_DEV_BUS_NAME in attrs:
            parentbus = (
                attrs[IFLAAttr.PARENT_DEV_BUS_NAME]
                .rstrip(b"\x00")
                .decode("utf-8", errors="replace")
            )
        if IFLAAttr.PARENT_DEV_NAME in attrs:
            parentdev = (
                attrs[IFLAAttr.PARENT_DEV_NAME]
                .rstrip(b"\x00")
                .decode("utf-8", errors="replace")
            )

        # Alternate names from IFLA_PROP_LIST
        altnames: list[str] = []
        if IFLAAttr.PROP_LIST in attrs:
            # PROP_LIST may contain multiple ALT_IFNAME entries
            # Since _parse_attrs only keeps last value, we need to iterate manually
            offset = 0
            prop_data = attrs[IFLAAttr.PROP_LIST]
            while offset + 4 <= len(prop_data):
                nla_len, nla_type = struct.unpack_from("HH", prop_data, offset)
                if nla_len < 4:
                    break
                nla_type_base = nla_type & 0x7FFF
                if nla_type_base == IFLAAttr.ALT_IFNAME:
                    attr_data = prop_data[offset + 4 : offset + nla_len]
                    altnames.append(
                        attr_data.rstrip(b"\x00").decode("utf-8", errors="replace")
                    )
                offset += (nla_len + 3) & ~3

        return ifname, LinkInfo(
            index=ifi_index,
            flags=ifi_flags,
            mtu=mtu,
            operstate=operstate,
            address=address,
            perm_address=perm_address,
            broadcast=broadcast,
            txqlen=txqlen,
            min_mtu=min_mtu,
            max_mtu=max_mtu,
            carrier=carrier,
            carrier_changes=carrier_changes,
            num_tx_queues=num_tx_queues,
            num_rx_queues=num_rx_queues,
            parentbus=parentbus,
            parentdev=parentdev,
            altnames=tuple(altnames),
        )

    def get_links(self) -> dict[str, LinkInfo]:
        """Get all network interfaces."""
        # Build ifinfomsg: family(1) + pad(1) + type(2) + index(4) + flags(4) + change(4) = 16 bytes
        ifinfomsg = struct.pack("BxHiII", AddressFamily.UNSPEC, 0, 0, 0, 0)
        # Add IFLA_EXT_MASK to request extended info but skip stats
        ext_mask = self._pack_nlattr_u32(
            IFLAAttr.EXT_MASK, RTEXTFilter.VF | RTEXTFilter.SKIP_STATS
        )
        payload = ifinfomsg + ext_mask
        msg = self._pack_nlmsg(
            RTMType.GETLINK, NLMsgFlags.REQUEST | NLMsgFlags.DUMP, payload
        )
        self._sock.send(msg)

        links: dict[str, LinkInfo] = {}
        for msg_type, payload in self._recv_msgs():
            if msg_type != RTMType.NEWLINK:
                continue
            if result := self._parse_link_payload(payload):
                ifname, link_info = result
                links[ifname] = link_info

        return links

    def get_link(self, name: str) -> LinkInfo:
        """Get link info for a single interface by name."""
        try:
            index = socket.if_nametoindex(name)
        except OSError:
            raise DeviceNotFound(f"No such device: {name}")

        # Build ifinfomsg with specific index
        # Use ACK flag to get a terminating response (no DUMP = single interface)
        ifinfomsg = struct.pack("BxHiII", AddressFamily.UNSPEC, 0, index, 0, 0)
        msg = self._pack_nlmsg(
            RTMType.GETLINK, NLMsgFlags.REQUEST | NLMsgFlags.ACK, ifinfomsg
        )
        self._sock.send(msg)

        for msg_type, payload in self._recv_msgs():
            if msg_type != RTMType.NEWLINK:
                continue
            if result := self._parse_link_payload(payload):
                return result[1]

        raise DeviceNotFound(f"No such device: {name}")

    def _resolve_ifname(self, index: int, cache: dict[int, str | None]) -> str | None:
        """Resolve interface index to name, using cache to avoid repeated syscalls."""
        if index not in cache:
            try:
                cache[index] = socket.if_indextoname(index)
            except OSError:
                cache[index] = None
        return cache[index]

    def _parse_address_payload(
        self, payload: bytes, ifname_cache: dict[int, str | None] | None = None
    ) -> AddressInfo | None:
        """Parse a NEWADDR payload into AddressInfo. Returns None if invalid."""
        if len(payload) < 8:
            return None

        # Parse ifaddrmsg header
        ifa_family, ifa_prefixlen, ifa_flags, ifa_scope, ifa_index = struct.unpack_from(
            "BBBBI", payload, 0
        )
        # Parse attributes after ifaddrmsg (8 bytes)
        attrs = self._parse_attrs(payload, 8)

        # Get address - prefer IFA_ADDRESS, fall back to IFA_LOCAL
        address = None
        if IFAAttr.ADDRESS in attrs:
            address = self._format_address(ifa_family, attrs[IFAAttr.ADDRESS])
        elif IFAAttr.LOCAL in attrs:
            address = self._format_address(ifa_family, attrs[IFAAttr.LOCAL])
        if not address:
            return None

        local = None
        broadcast = None
        label = None
        ifname = None

        if IFAAttr.LOCAL in attrs:
            local = self._format_address(ifa_family, attrs[IFAAttr.LOCAL])
        if IFAAttr.BROADCAST in attrs:
            broadcast = self._format_address(ifa_family, attrs[IFAAttr.BROADCAST])
        if IFAAttr.LABEL in attrs:
            label = (
                attrs[IFAAttr.LABEL].rstrip(b"\x00").decode("utf-8", errors="replace")
            )

        if ifname_cache is not None:
            ifname = self._resolve_ifname(ifa_index, ifname_cache)

        # Extended fields
        proto = None
        valid_lft = None
        preferred_lft = None

        if IFAAttr.PROTO in attrs:
            proto = attrs[IFAAttr.PROTO][0]

        if IFAAttr.CACHEINFO in attrs and len(attrs[IFAAttr.CACHEINFO]) >= 8:
            # struct ifa_cacheinfo: ifa_prefered(u32), ifa_valid(u32), cstamp(u32), tstamp(u32)
            ifa_prefered, ifa_valid = struct.unpack("II", attrs[IFAAttr.CACHEINFO][:8])
            # 0xFFFFFFFF means forever - convert to None
            preferred_lft = None if ifa_prefered == 0xFFFFFFFF else ifa_prefered
            valid_lft = None if ifa_valid == 0xFFFFFFFF else ifa_valid

        return AddressInfo(
            family=ifa_family,
            prefixlen=ifa_prefixlen,
            address=address,
            broadcast=broadcast,
            flags=ifa_flags,
            scope=ifa_scope,
            index=ifa_index,
            ifname=ifname,
            local=local,
            label=label,
            proto=proto,
            valid_lft=valid_lft,
            preferred_lft=preferred_lft,
        )

    def get_addresses(self) -> list[AddressInfo]:
        """Get all addresses for all interfaces."""
        # Build ifaddrmsg: family(1) + prefixlen(1) + flags(1) + scope(1) + index(4) = 8 bytes
        ifaddrmsg = struct.pack("BBBBI", AddressFamily.UNSPEC, 0, 0, 0, 0)
        msg = self._pack_nlmsg(
            RTMType.GETADDR, NLMsgFlags.REQUEST | NLMsgFlags.DUMP, ifaddrmsg
        )
        self._sock.send(msg)

        addresses: list[AddressInfo] = []
        ifname_cache: dict[int, str | None] = {}
        for msg_type, payload in self._recv_msgs():
            if msg_type != RTMType.NEWADDR:
                continue
            if addr_info := self._parse_address_payload(payload, ifname_cache):
                addresses.append(addr_info)

        return addresses

    def get_link_addresses(self, name: str) -> list[AddressInfo]:
        """Get addresses for a single interface by name."""
        try:
            index = socket.if_nametoindex(name)
        except OSError:
            raise DeviceNotFound(f"No such device: {name}")

        # Enable strict checking so kernel filters by interface index
        self._sock.setsockopt(SOL_NETLINK, NetlinkSockOpt.GET_STRICT_CHK, 1)
        try:
            # Build ifaddrmsg with specific index - kernel will filter with strict check enabled
            ifaddrmsg = struct.pack("BBBBI", AddressFamily.UNSPEC, 0, 0, 0, index)
            msg = self._pack_nlmsg(
                RTMType.GETADDR, NLMsgFlags.REQUEST | NLMsgFlags.DUMP, ifaddrmsg
            )
            self._sock.send(msg)

            # Pre-populate cache with the known name for this index
            ifname_cache: dict[int, str | None] = {index: name}
            addresses: list[AddressInfo] = []
            for msg_type, payload in self._recv_msgs():
                if msg_type != RTMType.NEWADDR:
                    continue
                if addr_info := self._parse_address_payload(payload, ifname_cache):
                    addresses.append(addr_info)

            return addresses
        finally:
            # Reset strict checking so subsequent calls work normally
            self._sock.setsockopt(SOL_NETLINK, NetlinkSockOpt.GET_STRICT_CHK, 0)

    def _format_address(self, family: int, data: bytes) -> str | None:
        if family == AddressFamily.INET and len(data) >= 4:
            return socket.inet_ntop(socket.AF_INET, data[:4])
        elif family == AddressFamily.INET6 and len(data) >= 16:
            return socket.inet_ntop(socket.AF_INET6, data[:16])
        return None


def get_address_netlink() -> AddressNetlink:
    nl = _address_ctx.get()
    needs_reconnect = False
    if nl is None:
        needs_reconnect = True
    elif nl._sock is None:
        needs_reconnect = True
    else:
        try:
            if nl._sock.fileno() == -1:
                needs_reconnect = True
        except OSError:
            needs_reconnect = True
    if needs_reconnect:
        if nl is not None:
            try:
                nl.close()
            except OSError:
                pass
        nl = AddressNetlink()
        nl._connect()
        _address_ctx.set(nl)
    return nl


def close_address_netlink() -> None:
    nl = _address_ctx.get()
    if nl is not None:
        nl.close()
        _address_ctx.set(None)
