from __future__ import annotations

import contextlib
import errno
import os
import socket
import struct
from typing import Literal, TypedDict
import uuid

from middlewared.api.base import BaseModel
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError

from .client import NTPClient
from .enums import ChronyAddressFamily, ChronyPacketType, ChronyReply, ChronyRequest, Mode, State

# chronyd command and monitoring protocol, see candm.h in the chrony source
CHRONYD_RUN_DIR = '/run/chrony'
CHRONYD_SOCK = f'{CHRONYD_RUN_DIR}/chronyd.sock'
PROTO_VERSION = 6
REQUEST_HEADER = struct.Struct('!BBBBHHIII')
REPLY_HEADER = struct.Struct('!BBBBHHHHHHIII')
N_SOURCES = struct.Struct('!I')
SOURCE_DATA = struct.Struct('!16sH2xhHHHHHIIII')
# Indexed by RPY_SD_MD_* and RPY_SD_ST_*
MODES = (Mode.SERVER, Mode.PEER, Mode.LOCAL)
STATES = (
    State.BEST, State.NOT_SELECTABLE, State.FALSE_TICKER, State.TOO_VARIABLE, State.SELECTED, State.SELECTABLE
)


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
    mode: Literal['SERVER', 'PEER', 'LOCAL']
    state: Literal['BEST', 'SELECTED', 'SELECTABLE', 'FALSE_TICKER', 'TOO_VARIABLE', 'NOT_SELECTABLE']
    remote: str
    stratum: int
    poll_interval: int
    reach: int
    lastrx: int
    offset: float
    offset_measured: float
    jitter: float
    active: bool


def test_ntp_server(addr: str) -> bool:
    try:
        return bool(NTPClient(addr).make_request()['version'])
    except Exception:
        return False


def chrony_float(value: int) -> float:
    """Decode chrony's 32 bit float, a signed 7 bit exponent followed by a signed 25 bit coefficient"""
    exp, coef = value >> 25, value & 0x1ffffff
    if exp >= 1 << 6:
        exp -= 1 << 7
    if coef >= 1 << 24:
        coef -= 1 << 25
    return coef * 2.0 ** (exp - 25)


def parse_source_data(data: bytes) -> NTPPeerData | None:
    """Convert the payload of a SOURCE_DATA reply to a peer entry, same as chronyc sources does"""
    (
        addr, family, poll, stratum, state, mode, _flags, reach, lastrx, offset_measured, offset, jitter
    ) = SOURCE_DATA.unpack_from(data)
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
        'mode': MODES[mode].value,
        'state': STATES[state].value,
        'remote': remote,
        'stratum': stratum,
        'poll_interval': poll,
        'reach': reach,
        'lastrx': lastrx,
        'offset': chrony_float(offset),
        'offset_measured': chrony_float(offset_measured),
        'jitter': chrony_float(jitter),
        'active': STATES[state].is_active(),
    }


def chronyd_request(
    sock: socket.socket, seq: int, command: ChronyRequest, body: bytes, reply: ChronyReply, length: int
) -> bytes:
    request = REQUEST_HEADER.pack(PROTO_VERSION, ChronyPacketType.REQUEST, 0, 0, command, 0, seq, 0, 0) + body
    # chronyd ignores requests that are shorter than their reply
    sock.send(request.ljust(REPLY_HEADER.size + length, b'\0'))
    data = sock.recv(1024)
    if len(data) < REPLY_HEADER.size:
        raise CallError('Truncated reply from chronyd')

    version, pkt_type, res1, res2, rcommand, rreply, status, _, _, _, rseq, _, _ = REPLY_HEADER.unpack_from(data)
    if (version, pkt_type, res1, res2, rcommand, rreply, status, rseq) != (
        PROTO_VERSION, ChronyPacketType.REPLY, 0, 0, command, reply, 0, seq
    ):
        raise CallError(f'Unexpected reply from chronyd: command={rcommand} reply={rreply} status={status}')

    payload = data[REPLY_HEADER.size:]
    if len(payload) < length:
        raise CallError('Truncated reply from chronyd')

    return payload


def query_chronyd_sources() -> list[bytes]:
    # chronyd replies to the path the client is bound to, this is what chronyc does as well
    path = f'{CHRONYD_RUN_DIR}/middlewared.{uuid.uuid4().hex}.sock'
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        try:
            sock.bind(path)
            # chronyd is unprivileged and needs write access to the socket to reply. It owns the directory,
            # do not follow a symlink it could have put in place of the socket.
            os.chmod(path, 0o666, follow_symlinks=False)
            sock.connect(CHRONYD_SOCK)
            n_sources, = N_SOURCES.unpack_from(
                chronyd_request(sock, 0, ChronyRequest.N_SOURCES, b'', ChronyReply.N_SOURCES, N_SOURCES.size)
            )
            return [
                chronyd_request(
                    sock, i + 1, ChronyRequest.SOURCE_DATA, N_SOURCES.pack(i), ChronyReply.SOURCE_DATA,
                    SOURCE_DATA.size
                )
                for i in range(n_sources)
            ]
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)


def get_peers(context: ServiceContext) -> list[NTPPeerData]:
    peers: list[NTPPeerData] = []

    if not context.middleware.call_sync('system.ready'):
        return peers

    try:
        sources = query_chronyd_sources()
    except OSError as e:
        raise CallError(
            f'Failed to query chronyd: {e}',
            errno.ECONNREFUSED if isinstance(e, (ConnectionRefusedError, FileNotFoundError)) else errno.EFAULT
        )

    for source in sources:
        try:
            peer = parse_source_data(source)
        except IndexError:
            context.logger.debug("Unexpected peer result: %s", source.hex())
            continue

        if peer is not None:
            peers.append(peer)

    return peers
