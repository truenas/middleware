from asyncio import Lock as AsyncioLock
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Union


LOCKED_XID_TTL = 3600


@dataclass(slots=True)
class ReservedXid:
    in_flight: dict[int, int]
    lock: Union[Lock, AsyncioLock]

    def available(self, xid: int) -> bool:
        if (expiry := self.in_flight.get(xid)) is None:
            return True

        return monotonic() > expiry

    def add_entry(self, xid: int) -> None:
        assert self.available(xid)
        self.in_flight[xid] = monotonic() + LOCKED_XID_TTL

    def remove_entry(self, xid: int) -> None:
        self.in_flight.pop(xid, None)

    def in_use(self) -> set:
        return set([entry for entry in self.in_flight.keys() if not self.available(entry)])


# WARNING: the lock type for this dataclass will need to update if changed from sync to async
# or vice-versa
ReservedUids = ReservedXid({}, Lock())
ReservedGids = ReservedXid({}, AsyncioLock())
