from __future__ import annotations

from collections.abc import Iterator
import contextlib
import errno
import itertools
import os
import socket
import struct
from typing import Literal, TypedDict
import uuid

from middlewared.api.base import BaseModel
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError

from .client import NTPClient
from .enums import ChronyAddressFamily, ChronyAuthMode, ChronyPacketType, ChronyReply, ChronyRequest, Mode, State

# chronyd command and monitoring protocol, see candm.h in the chrony source
CHRONYD_RUN_DIR = "/run/chrony"
CHRONYD_SOCK = f"{CHRONYD_RUN_DIR}/chronyd.sock"
PROTO_VERSION = 6
REQUEST_HEADER = struct.Struct("!BBBBHHIII")
REPLY_HEADER = struct.Struct("!BBBBHHHHHHIII")
N_SOURCES = struct.Struct("!I")
SOURCE_DATA = struct.Struct("!16sH2xhHHHHHIIII")
# A SOURCE_DATA reply starts with the source's address, which AUTH_DATA and NTP_SOURCE_NAME requests take as is
IP_ADDR_LENGTH = 20
AUTH_DATA = struct.Struct("!HHIHHIHHHH")
SOURCE_NAME = struct.Struct("!256s")
# What AUTH_DATA reports as the time since the last key establishment before the first one succeeds
NEVER = 0xFFFFFFFF
# Indexed by RPY_SD_MD_* and RPY_SD_ST_*
MODES = (Mode.SERVER, Mode.PEER, Mode.LOCAL)
STATES = (State.BEST, State.NOT_SELECTABLE, State.FALSE_TICKER, State.TOO_VARIABLE, State.SELECTED, State.SELECTABLE)


class NTPPeerData(TypedDict):
    mode: str
    state: str
    remote: str
    stratum: int
    poll_interval: int
    reach: int
    lastrx: int
    offset: float
    offset_measured: float
    jitter: float
    active: bool


class NTPPeerEntry(BaseModel):
    mode: Literal["SERVER", "PEER", "LOCAL"]
    state: Literal["BEST", "SELECTED", "SELECTABLE", "FALSE_TICKER", "TOO_VARIABLE", "NOT_SELECTABLE"]
    remote: str
    stratum: int
    poll_interval: int
    reach: int
    lastrx: int
    offset: float
    offset_measured: float
    jitter: float
    active: bool


class NTSAuthData(TypedDict):
    name: str
    key_length: int
    cookies: int
    attempts: int
    last_success: int | None


def test_ntp_server(addr: str, port: int = 123) -> bool:
    try:
        return bool(NTPClient(addr, port).make_request()["version"])
    except Exception:
        return False


def chrony_float(value: int) -> float:
    """Decode chrony's 32 bit float, a signed 7 bit exponent followed by a signed 25 bit coefficient"""
    exp, coef = value >> 25, value & 0x1FFFFFF
    if exp >= 1 << 6:
        exp -= 1 << 7
    if coef >= 1 << 24:
        coef -= 1 << 25
    return coef * 2.0 ** (exp - 25)


def parse_source_data(data: bytes) -> NTPPeerData | None:
    """Convert the payload of a SOURCE_DATA reply to a peer entry, same as chronyc sources does"""
    (addr, family, poll, stratum, state, mode, _flags, reach, lastrx, offset_measured, offset, jitter) = (
        SOURCE_DATA.unpack_from(data)
    )
    if family == ChronyAddressFamily.INET4:
        if MODES[mode] is Mode.LOCAL:
            # Reference clocks carry their refid in place of an address
            remote = bytes(c for c in addr[:4] if 32 <= c < 127).decode()
        else:
            remote = socket.inet_ntop(socket.AF_INET, addr[:4])
    elif family == ChronyAddressFamily.INET6:
        remote = socket.inet_ntop(socket.AF_INET6, addr)
    else:
        # Source that is not resolved yet
        return None

    return {
        "mode": MODES[mode].value,
        "state": STATES[state].value,
        "remote": remote,
        "stratum": stratum,
        "poll_interval": poll,
        "reach": reach,
        "lastrx": lastrx,
        "offset": chrony_float(offset),
        "offset_measured": chrony_float(offset_measured),
        "jitter": chrony_float(jitter),
        "active": STATES[state].is_active(),
    }


def parse_auth_data(name: str, data: bytes) -> NTSAuthData:
    """Convert the payload of an AUTH_DATA reply for an NTS source, same as chronyc authdata does"""
    _mode, _key_type, _key_id, key_length, attempts, last_ke_ago, cookies, _cookie_length, _nak, _pad = (
        AUTH_DATA.unpack_from(data)
    )
    return {
        "name": name,
        "key_length": key_length,
        "cookies": cookies,
        "attempts": attempts,
        "last_success": None if last_ke_ago == NEVER else last_ke_ago,
    }


def parse_source_name(data: bytes) -> str:
    """The name a source is configured with, from the payload of an NTP_SOURCE_NAME reply, same as chronyc -N"""
    raw: bytes = SOURCE_NAME.unpack_from(data)[0]
    name, terminated, _ = raw.partition(b"\0")
    # Like chronyc, do not trust a name that is not terminated or not printable
    if not terminated or not name or not all(0x21 <= c <= 0x7E for c in name):
        return "?"

    return name.decode()


def chronyd_request(
    sock: socket.socket, seq: int, command: ChronyRequest, body: bytes, reply: ChronyReply, length: int
) -> bytes:
    request = REQUEST_HEADER.pack(PROTO_VERSION, ChronyPacketType.REQUEST, 0, 0, command, 0, seq, 0, 0) + body
    # chronyd ignores requests that are shorter than their reply
    sock.send(request.ljust(REPLY_HEADER.size + length, b"\0"))
    data = sock.recv(1024)
    if len(data) < REPLY_HEADER.size:
        raise CallError("Truncated reply from chronyd")

    version, pkt_type, res1, res2, rcommand, rreply, status, _, _, _, rseq, _, _ = REPLY_HEADER.unpack_from(data)
    if (version, pkt_type, res1, res2, rcommand, rreply, status, rseq) != (
        PROTO_VERSION,
        ChronyPacketType.REPLY,
        0,
        0,
        command,
        reply,
        0,
        seq,
    ):
        raise CallError(f"Unexpected reply from chronyd: command={rcommand} reply={rreply} status={status}")

    payload = data[REPLY_HEADER.size :]
    if len(payload) < length:
        raise CallError("Truncated reply from chronyd")

    return payload


@contextlib.contextmanager
def chronyd_socket() -> Iterator[socket.socket]:
    # chronyd replies to the path the client is bound to, this is what chronyc does as well
    path = f"{CHRONYD_RUN_DIR}/middlewared.{uuid.uuid4().hex}.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        try:
            sock.bind(path)
            # chronyd is unprivileged and needs write access to the socket to reply. It owns the directory,
            # do not follow a symlink it could have put in place of the socket.
            os.chmod(path, 0o666, follow_symlinks=False)
            sock.connect(CHRONYD_SOCK)
            yield sock
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)


def chronyd_sources(sock: socket.socket, seq: Iterator[int]) -> list[bytes]:
    """The SOURCE_DATA payloads of all of chronyd's sources"""
    (n_sources,) = N_SOURCES.unpack_from(
        chronyd_request(sock, next(seq), ChronyRequest.N_SOURCES, b"", ChronyReply.N_SOURCES, N_SOURCES.size)
    )
    return [
        chronyd_request(
            sock, next(seq), ChronyRequest.SOURCE_DATA, N_SOURCES.pack(i), ChronyReply.SOURCE_DATA, SOURCE_DATA.size
        )
        for i in range(n_sources)
    ]


def query_chronyd_sources() -> list[bytes]:
    with chronyd_socket() as sock:
        return chronyd_sources(sock, itertools.count())


def chronyd_nts_sources(sock: socket.socket) -> list[NTSAuthData]:
    """The authentication state of the sources that use NTS, same as chronyc -N authdata -a"""
    seq = itertools.count()
    sources: list[NTSAuthData] = []
    for source in chronyd_sources(sock, seq):
        mode = SOURCE_DATA.unpack_from(source)[5]
        if mode >= len(MODES) or MODES[mode] is Mode.LOCAL:
            # Reference clocks are not authenticated
            continue

        # Unlike chronyc sources, keep the sources that are not resolved yet: chronyd knows them by an ID, and a name
        # that does not resolve is a reason for NTS to fail
        ip_addr = source[:IP_ADDR_LENGTH]
        auth = chronyd_request(sock, next(seq), ChronyRequest.AUTH_DATA, ip_addr, ChronyReply.AUTH_DATA, AUTH_DATA.size)
        if AUTH_DATA.unpack_from(auth)[0] != ChronyAuthMode.NTS:
            continue

        name = chronyd_request(
            sock, next(seq), ChronyRequest.NTP_SOURCE_NAME, ip_addr, ChronyReply.NTP_SOURCE_NAME, SOURCE_NAME.size
        )
        sources.append(parse_auth_data(parse_source_name(name), auth))

    return sources


def chronyd_error(error: OSError) -> CallError:
    return CallError(
        f"Failed to query chronyd: {error}",
        errno.ECONNREFUSED if isinstance(error, (ConnectionRefusedError, FileNotFoundError)) else errno.EFAULT,
    )


def get_peers(context: ServiceContext) -> list[NTPPeerData]:
    peers: list[NTPPeerData] = []

    if not context.middleware.call_sync("system.ready"):
        return peers

    try:
        sources = query_chronyd_sources()
    except OSError as e:
        raise chronyd_error(e)

    for source in sources:
        try:
            peer = parse_source_data(source)
        except IndexError:
            context.logger.debug("Unexpected peer result: %s", source.hex())
            continue

        if peer is not None:
            peers.append(peer)

    return peers


def get_nts_authdata(context: ServiceContext) -> list[NTSAuthData]:
    """NTS key establishment state of every source that uses NTS, by the name it is configured with"""
    if not context.middleware.call_sync("system.ready"):
        return []

    try:
        with chronyd_socket() as sock:
            return chronyd_nts_sources(sock)
    except OSError as e:
        raise chronyd_error(e)
