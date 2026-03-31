from typing import Literal

from middlewared.api.base import BaseModel


__all__ = [
    "ZpoolScrubEntry",
    "ZpoolScrubArgs",
    "ZpoolScrubResult",
]


class ZpoolScrubEntry(BaseModel):
    pool_name: str
    """Name of the zpool."""
    scan_type: Literal["SCRUB", "ERRORSCRUB"] = "SCRUB"
    """SCRUB: full data integrity scan. ERRORSCRUB: targeted scan of blocks with known errors."""
    action: Literal["START", "PAUSE", "CANCEL"] = "START"
    """START: begin or resume. PAUSE: pause in-progress scan. CANCEL: stop entirely."""
    wait: bool = False
    """If True and action is START, poll scrub progress until completion. Ignored for PAUSE/CANCEL."""


class ZpoolScrubArgs(BaseModel):
    data: ZpoolScrubEntry


class ZpoolScrubResult(BaseModel):
    result: None
