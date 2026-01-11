import socket
import struct
import threading
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType

from .constants import (
    CTRL_ATTR_FAMILY_ID,
    CTRL_ATTR_FAMILY_NAME,
    CTRL_CMD_GETFAMILY,
    ETH_SS_FEATURES,
    ETH_SS_LINK_MODES,
    ETHTOOL_A_BITSET_BIT_INDEX,
    ETHTOOL_A_BITSET_BIT_VALUE,
    ETHTOOL_A_BITSET_BITS,
    ETHTOOL_A_BITSET_BITS_BIT,
    ETHTOOL_A_BITSET_MASK,
    ETHTOOL_A_BITSET_SIZE,
    ETHTOOL_A_BITSET_VALUE,
    ETHTOOL_A_FEATURES_ACTIVE,
    ETHTOOL_A_FEATURES_HW,
    ETHTOOL_A_FEATURES_NOCHANGE,
    ETHTOOL_A_HEADER,
    ETHTOOL_A_HEADER_DEV_NAME,
    ETHTOOL_A_HEADER_FLAGS,
    ETHTOOL_A_LINKINFO_PHYADDR,
    ETHTOOL_A_LINKINFO_PORT,
    ETHTOOL_A_LINKINFO_TRANSCEIVER,
    ETHTOOL_A_LINKMODES_AUTONEG,
    ETHTOOL_A_LINKMODES_DUPLEX,
    ETHTOOL_A_LINKMODES_OURS,
    ETHTOOL_A_LINKMODES_SPEED,
    ETHTOOL_A_LINKSTATE_LINK,
    ETHTOOL_A_STRING_INDEX,
    ETHTOOL_A_STRING_VALUE,
    ETHTOOL_A_STRINGSET_ID,
    ETHTOOL_A_STRINGSET_STRINGS,
    ETHTOOL_A_STRINGSETS_STRINGSET,
    ETHTOOL_A_STRINGS_STRING,
    ETHTOOL_A_STRSET_STRINGSETS,
    ETHTOOL_MSG_FEATURES_GET,
    ETHTOOL_MSG_LINKINFO_GET,
    ETHTOOL_MSG_LINKMODES_GET,
    ETHTOOL_MSG_LINKSTATE_GET,
    ETHTOOL_MSG_STRSET_GET,
    GENL_ID_CTRL,
    NETLINK_GENERIC,
    NLA_F_NESTED,
    NLM_F_ACK,
    NLM_F_REQUEST,
    NLMSG_ERROR,
)

_link_mode_names: MappingProxyType[int, str] | None = None
_feature_names: MappingProxyType[int, str] | None = None
_cache_init_lock = threading.Lock()
_ethtool_ctx: ContextVar["EthtoolNetlink | None"] = ContextVar("ethtool", default=None)


class PortType(IntEnum):
    TP = 0x00
    AUI = 0x01
    MII = 0x02
    FIBRE = 0x03
    BNC = 0x04
    DA = 0x05
    NONE = 0xEF
    OTHER = 0xFF


PORT_TYPE_NAMES: MappingProxyType = MappingProxyType({
    PortType.TP: "Twisted Pair",
    PortType.AUI: "AUI",
    PortType.MII: "MII",
    PortType.FIBRE: "Fibre",
    PortType.BNC: "BNC",
    PortType.DA: "Direct Attach Copper",
    PortType.NONE: "None",
    PortType.OTHER: "Other",
})


class Duplex(IntEnum):
    HALF = 0
    FULL = 1
    UNKNOWN = 0xFF


class Transceiver(IntEnum):
    INTERNAL = 0
    EXTERNAL = 1


class NetlinkError(Exception):
    pass


class DeviceNotFound(NetlinkError):
    pass


class OperationNotSupported(NetlinkError):
    pass


@dataclass(slots=True)
class EthtoolNetlink:
    _sock: socket.socket | None = field(default=None, init=False)
    _family_id: int | None = field(default=None, init=False)
    _seq: int = field(default=0, init=False)
    _pid: int | None = field(default=None, init=False)
    _feature_names: dict[int, str] | MappingProxyType[int, str] | None = field(default=None, init=False)
    _link_mode_names: dict[int, str] | MappingProxyType[int, str] | None = field(default=None, init=False)

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *args):
        self.close()

    def _connect(self):
        self._sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_GENERIC)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self._sock.bind((0, 0))
        self._pid = self._sock.getsockname()[0]
        self._family_id = self._resolve_family("ethtool")

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None
        self._feature_names = None
        self._link_mode_names = None

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

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
        return self._pack_nlattr(attr_type | NLA_F_NESTED, attrs)

    def _pack_nlmsg(self, msg_type: int, flags: int, payload: bytes) -> bytes:
        seq = self._next_seq()
        nlmsg_len = 16 + len(payload)
        return struct.pack("IHHII", nlmsg_len, msg_type, flags, seq, 0) + payload

    def _pack_genlmsg(self, family_id: int, cmd: int, version: int, attrs: bytes) -> bytes:
        genlhdr = struct.pack("BBH", cmd, version, 0)
        payload = genlhdr + attrs
        return self._pack_nlmsg(family_id, NLM_F_REQUEST | NLM_F_ACK, payload)

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
                if nlmsg_type == NLMSG_ERROR:
                    if offset + 20 <= len(data):
                        error = struct.unpack_from("i", data, offset + 16)[0]
                        if error < 0:
                            error = -error
                            if error == 19:
                                raise DeviceNotFound("No such device")
                            elif error == 95:
                                raise OperationNotSupported("Operation not supported")
                            raise NetlinkError(f"Netlink error: {error}")
                    done = True
                elif nlmsg_type == 0x03:
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

    def _resolve_family(self, name: str) -> int:
        attrs = self._pack_nlattr_str(CTRL_ATTR_FAMILY_NAME, name)
        msg = self._pack_genlmsg(GENL_ID_CTRL, CTRL_CMD_GETFAMILY, 1, attrs)
        self._sock.send(msg)
        for msg_type, payload in self._recv_msgs():
            if msg_type == GENL_ID_CTRL:
                attrs = self._parse_attrs(payload, 4)
                if CTRL_ATTR_FAMILY_ID in attrs:
                    return struct.unpack("H", attrs[CTRL_ATTR_FAMILY_ID][:2])[0]
        raise NetlinkError(f"Could not resolve family: {name}")

    def _make_header(self, ifname: str, flags: int = 0) -> bytes:
        name_attr = self._pack_nlattr_str(ETHTOOL_A_HEADER_DEV_NAME, ifname)
        if flags:
            name_attr += self._pack_nlattr_u32(ETHTOOL_A_HEADER_FLAGS, flags)
        return self._pack_nlattr_nested(ETHTOOL_A_HEADER, name_attr)

    def _parse_bitset(self, data: bytes) -> tuple[int, set[int], set[int]]:
        attrs = self._parse_nested_attrs(data)
        size = 0
        if ETHTOOL_A_BITSET_SIZE in attrs:
            size = struct.unpack("I", attrs[ETHTOOL_A_BITSET_SIZE][:4])[0]
        value_bits: set[int] = set()
        mask_bits: set[int] = set()
        if ETHTOOL_A_BITSET_VALUE in attrs:
            value_data = attrs[ETHTOOL_A_BITSET_VALUE]
            for byte_idx, byte_val in enumerate(value_data):
                for bit in range(8):
                    if byte_val & (1 << bit):
                        value_bits.add(byte_idx * 8 + bit)
        if ETHTOOL_A_BITSET_MASK in attrs:
            mask_data = attrs[ETHTOOL_A_BITSET_MASK]
            for byte_idx, byte_val in enumerate(mask_data):
                for bit in range(8):
                    if byte_val & (1 << bit):
                        mask_bits.add(byte_idx * 8 + bit)
        if ETHTOOL_A_BITSET_BITS in attrs:
            bits_data = attrs[ETHTOOL_A_BITSET_BITS]
            offset = 0
            while offset + 4 <= len(bits_data):
                nla_len, nla_type = struct.unpack_from("HH", bits_data, offset)
                if nla_len < 4:
                    break
                if (nla_type & 0x7FFF) == ETHTOOL_A_BITSET_BITS_BIT:
                    bit_data = bits_data[offset + 4 : offset + nla_len]
                    bit_attrs = self._parse_nested_attrs(bit_data)
                    bit_index = None
                    bit_value = True
                    if ETHTOOL_A_BITSET_BIT_INDEX in bit_attrs:
                        bit_index = struct.unpack("I", bit_attrs[ETHTOOL_A_BITSET_BIT_INDEX][:4])[0]
                    if ETHTOOL_A_BITSET_BIT_VALUE in bit_attrs:
                        val_data = bit_attrs[ETHTOOL_A_BITSET_BIT_VALUE]
                        if len(val_data) > 0:
                            bit_value = val_data[0] != 0
                    if bit_index is not None and bit_value:
                        value_bits.add(bit_index)
                    if bit_index is not None:
                        mask_bits.add(bit_index)
                offset += (nla_len + 3) & ~3
        return size, value_bits, mask_bits

    def get_link_modes(self, ifname: str) -> dict:
        link_mode_names = self._get_link_mode_names()
        header = self._make_header(ifname)
        msg = self._pack_genlmsg(self._family_id, ETHTOOL_MSG_LINKMODES_GET, 1, header)
        self._sock.send(msg)
        result = {
            "speed": None,
            "duplex": "Unknown",
            "autoneg": False,
            "supported_modes": [],
        }
        for msg_type, payload in self._recv_msgs():
            if msg_type == self._family_id:
                attrs = self._parse_attrs(payload, 4)
                if ETHTOOL_A_LINKMODES_SPEED in attrs:
                    speed = struct.unpack("I", attrs[ETHTOOL_A_LINKMODES_SPEED][:4])[0]
                    if speed != 0xFFFFFFFF:
                        result["speed"] = speed
                if ETHTOOL_A_LINKMODES_DUPLEX in attrs:
                    duplex = attrs[ETHTOOL_A_LINKMODES_DUPLEX][0]
                    if duplex == Duplex.FULL:
                        result["duplex"] = "Full"
                    elif duplex == Duplex.HALF:
                        result["duplex"] = "Half"
                if ETHTOOL_A_LINKMODES_AUTONEG in attrs:
                    result["autoneg"] = attrs[ETHTOOL_A_LINKMODES_AUTONEG][0] == 1
                if ETHTOOL_A_LINKMODES_OURS in attrs:
                    _, value_bits, _ = self._parse_bitset(attrs[ETHTOOL_A_LINKMODES_OURS])
                    modes = []
                    for bit in sorted(value_bits):
                        if bit in link_mode_names:
                            modes.append(link_mode_names[bit])
                    result["supported_modes"] = modes
        return result

    def get_link_info(self, ifname: str) -> dict:
        header = self._make_header(ifname)
        msg = self._pack_genlmsg(self._family_id, ETHTOOL_MSG_LINKINFO_GET, 1, header)
        self._sock.send(msg)
        result = {
            "port": "Unknown",
            "port_num": 0,
            "transceiver": "internal",
            "phyaddr": None,
        }
        for msg_type, payload in self._recv_msgs():
            if msg_type == self._family_id:
                attrs = self._parse_attrs(payload, 4)
                if ETHTOOL_A_LINKINFO_PORT in attrs:
                    port = attrs[ETHTOOL_A_LINKINFO_PORT][0]
                    result["port_num"] = port
                    result["port"] = PORT_TYPE_NAMES.get(port, f"Unknown({port})")
                if ETHTOOL_A_LINKINFO_TRANSCEIVER in attrs:
                    xcvr = attrs[ETHTOOL_A_LINKINFO_TRANSCEIVER][0]
                    result["transceiver"] = "external" if xcvr == Transceiver.EXTERNAL else "internal"
                if ETHTOOL_A_LINKINFO_PHYADDR in attrs:
                    result["phyaddr"] = attrs[ETHTOOL_A_LINKINFO_PHYADDR][0]
        return result

    def get_link_state(self, ifname: str) -> bool:
        header = self._make_header(ifname)
        msg = self._pack_genlmsg(self._family_id, ETHTOOL_MSG_LINKSTATE_GET, 1, header)
        self._sock.send(msg)
        for msg_type, payload in self._recv_msgs():
            if msg_type == self._family_id:
                attrs = self._parse_attrs(payload, 4)
                if ETHTOOL_A_LINKSTATE_LINK in attrs:
                    return attrs[ETHTOOL_A_LINKSTATE_LINK][0] == 1
        return False

    def _query_string_set(self, string_set_id: int, ifname: str = "lo") -> dict[int, str]:
        stringset_id = self._pack_nlattr_u32(ETHTOOL_A_STRINGSET_ID, string_set_id)
        stringset = self._pack_nlattr_nested(ETHTOOL_A_STRINGSETS_STRINGSET, stringset_id)
        stringsets = self._pack_nlattr_nested(ETHTOOL_A_STRSET_STRINGSETS, stringset)
        header = self._make_header(ifname)
        msg = self._pack_genlmsg(self._family_id, ETHTOOL_MSG_STRSET_GET, 1, header + stringsets)
        self._sock.send(msg)
        names: dict[int, str] = {}
        for msg_type, payload in self._recv_msgs():
            if msg_type == self._family_id:
                attrs = self._parse_attrs(payload, 4)
                if ETHTOOL_A_STRSET_STRINGSETS in attrs:
                    self._parse_stringsets(attrs[ETHTOOL_A_STRSET_STRINGSETS], names)
        return names

    def _get_feature_names(self) -> dict[int, str] | MappingProxyType[int, str]:
        if self._feature_names is not None:
            return self._feature_names
        self._feature_names = self._query_string_set(ETH_SS_FEATURES)
        return self._feature_names

    def _get_link_mode_names(self) -> dict[int, str] | MappingProxyType[int, str]:
        if self._link_mode_names is not None:
            return self._link_mode_names
        self._link_mode_names = self._query_string_set(ETH_SS_LINK_MODES)
        return self._link_mode_names

    def _parse_stringsets(self, data: bytes, names: dict[int, str]):
        offset = 0
        while offset + 4 <= len(data):
            nla_len, nla_type = struct.unpack_from("HH", data, offset)
            if nla_len < 4:
                break
            if (nla_type & 0x7FFF) == ETHTOOL_A_STRINGSETS_STRINGSET:
                self._parse_stringset(data[offset + 4 : offset + nla_len], names)
            offset += (nla_len + 3) & ~3

    def _parse_stringset(self, data: bytes, names: dict[int, str]):
        attrs = self._parse_nested_attrs(data)
        if ETHTOOL_A_STRINGSET_STRINGS in attrs:
            self._parse_strings(attrs[ETHTOOL_A_STRINGSET_STRINGS], names)

    def _parse_strings(self, data: bytes, names: dict[int, str]):
        offset = 0
        while offset + 4 <= len(data):
            nla_len, nla_type = struct.unpack_from("HH", data, offset)
            if nla_len < 4:
                break
            if (nla_type & 0x7FFF) == ETHTOOL_A_STRINGS_STRING:
                string_attrs = self._parse_nested_attrs(data[offset + 4 : offset + nla_len])
                if ETHTOOL_A_STRING_INDEX in string_attrs and ETHTOOL_A_STRING_VALUE in string_attrs:
                    idx = struct.unpack("I", string_attrs[ETHTOOL_A_STRING_INDEX][:4])[0]
                    val = string_attrs[ETHTOOL_A_STRING_VALUE].rstrip(b"\x00").decode("utf-8", errors="replace")
                    names[idx] = val
            offset += (nla_len + 3) & ~3

    def get_features(self, ifname: str) -> dict:
        feature_names = self._get_feature_names()
        header = self._make_header(ifname)
        msg = self._pack_genlmsg(self._family_id, ETHTOOL_MSG_FEATURES_GET, 1, header)
        self._sock.send(msg)
        result: dict[str, list[str]] = {"enabled": [], "disabled": [], "supported": []}
        hw_bits: set[int] = set()
        active_bits: set[int] = set()
        nochange_bits: set[int] = set()
        for msg_type, payload in self._recv_msgs():
            if msg_type == self._family_id:
                attrs = self._parse_attrs(payload, 4)
                if ETHTOOL_A_FEATURES_HW in attrs:
                    _, hw_bits, _ = self._parse_bitset(attrs[ETHTOOL_A_FEATURES_HW])
                if ETHTOOL_A_FEATURES_ACTIVE in attrs:
                    _, active_bits, _ = self._parse_bitset(attrs[ETHTOOL_A_FEATURES_ACTIVE])
                if ETHTOOL_A_FEATURES_NOCHANGE in attrs:
                    _, nochange_bits, _ = self._parse_bitset(attrs[ETHTOOL_A_FEATURES_NOCHANGE])
        for idx in hw_bits:
            name = feature_names.get(idx, f"feature-{idx}")
            if idx not in nochange_bits:
                result["supported"].append(name)
            if idx in active_bits:
                result["enabled"].append(name)
            else:
                result["disabled"].append(name)
        return result


def _ensure_global_caches() -> tuple[MappingProxyType[int, str], MappingProxyType[int, str]]:
    global _link_mode_names, _feature_names
    if _link_mode_names is not None and _feature_names is not None:
        return _link_mode_names, _feature_names
    with _cache_init_lock:
        if _link_mode_names is not None and _feature_names is not None:
            return _link_mode_names, _feature_names
        with EthtoolNetlink() as eth:
            _link_mode_names = MappingProxyType(eth._query_string_set(ETH_SS_LINK_MODES))
            _feature_names = MappingProxyType(eth._query_string_set(ETH_SS_FEATURES))
        return _link_mode_names, _feature_names


def get_ethtool() -> EthtoolNetlink:
    eth = _ethtool_ctx.get()
    needs_reconnect = False
    if eth is None:
        needs_reconnect = True
    elif eth._sock is None:
        needs_reconnect = True
    else:
        try:
            if eth._sock.fileno() == -1:
                needs_reconnect = True
        except OSError:
            needs_reconnect = True
    if needs_reconnect:
        if eth is not None:
            try:
                eth.close()
            except OSError:
                pass
        link_modes, features = _ensure_global_caches()
        eth = EthtoolNetlink()
        eth._connect()
        eth._link_mode_names = link_modes
        eth._feature_names = features
        _ethtool_ctx.set(eth)
    return eth


def close_ethtool() -> None:
    eth = _ethtool_ctx.get()
    if eth is not None:
        eth.close()
        _ethtool_ctx.set(None)
