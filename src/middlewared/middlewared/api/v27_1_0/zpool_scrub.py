from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = [
    "ZpoolScrubRun",
    "ZpoolScrubRunArgs",
    "ZpoolScrubRunResult",
]


class ZpoolScrubRun(BaseModel):
    pool_name: str = Field(description="Name of the zpool.")
    scan_type: Literal["SCRUB", "ERRORSCRUB"] = Field(
        default="SCRUB",
        description="SCRUB: full data integrity scan. ERRORSCRUB: targeted scan of blocks with known errors.",
    )
    action: Literal["START", "PAUSE", "CANCEL"] = Field(
        default="START",
        description="START: begin or resume. PAUSE: pause in-progress scan. CANCEL: stop entirely.",
    )
    threshold: int = Field(default=35, description="Days before a scrub is due when the scrub should start.")


class ZpoolScrubRunArgs(BaseModel):
    data: ZpoolScrubRun = Field(description="Scrub run parameters.")


class ZpoolScrubRunResult(BaseModel):
    result: None
