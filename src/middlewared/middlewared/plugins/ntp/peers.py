from __future__ import annotations

import errno
import subprocess
from typing import Any, Literal

from middlewared.api.base import BaseModel
from middlewared.service import ServiceContext, ValidationErrors
from middlewared.service_exception import CallError

from .client import NTPClient
from .enums import Mode, State


class NTPPeer:
    def __init__(self, initial_data: dict[str, Any]) -> None:
        self._mode = Mode.from_str(initial_data['mode'])
        self._state = State.from_str(initial_data['state'])
        self._remote: str = initial_data['remote']
        self._stratum: int = initial_data['stratum']
        self._poll_interval: int = initial_data['poll_interval']
        self._reach: int = initial_data['reach']
        self._lastrx: int = initial_data['lastrx']
        self._offset: float = initial_data['offset']
        self._offset_measured: float = initial_data['offset_measured']
        self._jitter: float = initial_data['jitter']

    @classmethod
    def from_chronyc_sources(
        cls,
        mode: str,
        state: str,
        remote: str,
        stratum: str,
        poll_interval: str,
        reach: str,
        lastrx: str,
        offset: str,
        offset_measured: str,
        jitter: str,
    ) -> NTPPeer:
        """Construct a NTPPeer object from one line of output from chronyc sources -c"""
        return cls({
            'mode': mode,
            'state': state,
            'remote': remote,
            'stratum': int(stratum),
            'poll_interval': int(poll_interval),
            'reach': int(reach, 8),
            'lastrx': int(lastrx),
            'offset': float(offset),
            'offset_measured': float(offset_measured),
            'jitter': float(jitter)
        })

    def asdict(self) -> dict[str, Any]:
        return {
            'mode': str(self._mode),
            'state': str(self._state),
            'remote': self._remote,
            'stratum': self._stratum,
            'poll_interval': self._poll_interval,
            'reach': self._reach,
            'lastrx': self._lastrx,
            'offset': self._offset,
            'offset_measured': self._offset_measured,
            'jitter': self._jitter,
            'active': self.is_active(),
        }

    def is_active(self) -> bool:
        return self._state.is_active()

    def __str__(self) -> str:
        return f"{self._mode}: {self._state} [{self._remote}]"

    @property
    def remote(self) -> str:
        return self._remote

    @property
    def offset_in_secs(self) -> float:
        return self._offset


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


def get_peers(context: ServiceContext) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []

    if not context.middleware.call_sync('system.ready'):
        return peers

    resp = subprocess.run(['chronyc', '-c', 'sources'], capture_output=True)
    if resp.returncode != 0 or resp.stderr:
        errmsg = resp.stderr.decode().strip()
        raise CallError(
            errmsg,
            errno.ECONNREFUSED if "Connection refused" in errmsg else errno.EFAULT
        )

    for entry in resp.stdout.decode().splitlines():
        values = entry.split(',')
        if len(values) != 10:
            context.logger.debug("Unexpected peer result: %s", entry)
            continue

        try:
            peer = NTPPeer.from_chronyc_sources(*values)
        except NotImplementedError as e:
            context.logger.debug("Unexpected item %s: %s", e, entry)
            continue
        except ValidationErrors as e:
            context.logger.debug("Invalid remote address: %s", e)
            continue

        peers.append(peer.asdict())

    return peers
