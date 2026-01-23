from dataclasses import dataclass
from time import monotonic


LOCKED_XID_TTL = 3600


@dataclass(slots=True)
class ReservedXid:
    in_flight: dict[int, float]

    def available(self, xid: int) -> bool:
        if (expiry := self.in_flight.get(xid)) is None:
            return True

        if monotonic() > expiry:
            self.in_flight.pop(xid, None)
            return True

        return False

    def add_entry(self, xid: int) -> None:
        assert self.available(xid)
        self.in_flight[xid] = monotonic() + LOCKED_XID_TTL

    def remove_entry(self, xid: int) -> None:
        self.in_flight.pop(xid, None)

    def in_use(self) -> set[int]:
        return set([entry for entry in list(self.in_flight.keys()) if not self.available(entry)])
