from typing import Literal

from middlewared.api.base import BaseModel


__all__ = [
    "ZpoolScrubRun",
    "ZpoolScrubRunArgs",
    "ZpoolScrubRunResult",
]


class ZpoolScrubRun(BaseModel):
    pool_name: str
    """Name of the zpool."""
    scan_type: Literal["SCRUB", "ERRORSCRUB"] = "SCRUB"
    """SCRUB: full data integrity scan. ERRORSCRUB: targeted scan of blocks with known errors."""
    action: Literal["START", "PAUSE", "CANCEL"] = "START"
    """START: begin or resume. PAUSE: pause in-progress scan. CANCEL: stop entirely."""
    wait: bool = False
    """If True and action is START, poll scrub progress until completion. Ignored for PAUSE/CANCEL."""
    threshold: int = 35
    """Days before a scrub is due when the scrub should start."""


class ZpoolScrubRunArgs(BaseModel):
    data: ZpoolScrubRun
    """Scrub run parameters."""


class ZpoolScrubRunResult(BaseModel):
    result: None
