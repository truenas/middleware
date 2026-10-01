from __future__ import annotations

import enum


class ChronyPacketType(enum.IntEnum):
    REQUEST = 1
    REPLY = 2


class ChronyRequest(enum.IntEnum):
    N_SOURCES = 14
    SOURCE_DATA = 15


class ChronyReply(enum.IntEnum):
    N_SOURCES = 2
    SOURCE_DATA = 3


class ChronyAddressFamily(enum.IntEnum):
    """Address families as chronyd numbers them, not the socket.AF_* values"""

    INET4 = 1
    INET6 = 2


class Mode(enum.Enum):
    SERVER = "SERVER"
    PEER = "PEER"
    LOCAL = "LOCAL"

    def __str__(self) -> str:
        return str(self.value)


class State(enum.Enum):
    BEST = "BEST"
    SELECTED = "SELECTED"
    SELECTABLE = "SELECTABLE"
    FALSE_TICKER = "FALSE_TICKER"
    TOO_VARIABLE = "TOO_VARIABLE"
    NOT_SELECTABLE = "NOT_SELECTABLE"

    def is_active(self) -> bool:
        return self in [State.BEST, State.SELECTED]

    def __str__(self) -> str:
        return str(self.value)
