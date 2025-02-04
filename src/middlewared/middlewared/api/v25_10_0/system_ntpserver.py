from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass
from typing import Literal


__all__ = [
    'NTPPeerEntry', 'NTPServerEntry',
    'NTPServerCreateArgs', 'NTPServerCreateResult',
    'NTPServerUpdateArgs', 'NTPServerUpdateResult',
    'NTPServerDeleteArgs', 'NTPServerDeleteResult',
]


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


class NTPServerEntry(BaseModel):
    id: int
    address: str
    burst: bool = False
    iburst: bool = True
    prefer: bool = False
    minpoll: int = 6
    maxpoll: int = 10


class NTPServerCreate(NTPServerEntry):
    id: Excluded = excluded_field()
    force: bool = False


class NTPServerUpdate(NTPServerCreate, metaclass=ForUpdateMetaclass):
    pass


class NTPServerCreateArgs(BaseModel):
    ntp_server_create: NTPServerCreate


class NTPServerUpdateArgs(BaseModel):
    id: int
    ntp_server_update: NTPServerUpdate


class NTPServerCreateResult(BaseModel):
    result: NTPServerEntry


class NTPServerUpdateResult(BaseModel):
    result: NTPServerEntry


class NTPServerDeleteArgs(BaseModel):
    id: int


class NTPServerDeleteResult(BaseModel):
    result: Literal[True]
