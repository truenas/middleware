from typing import Any

from middlewared.api.base import BaseModel

__all__ = ["AtaSelfTest", "NvmeSelfTest", "ScsiSelfTest"]

class AtaSelfTest(BaseModel):
    num: int
    description: str
    status: str
    status_verbose: str
    remaining: int
    lifetime: int
    lba_of_first_error: int | None = None

class NvmeSelfTest(BaseModel):
    num: int
    description: str
    status: str
    status_verbose: str
    power_on_hours: int
    failing_lba: int | None = None
    nsid: int | None = None
    seg: int | None = None
    sct: int | None = 0x0
    code: int | None = 0x0

class ScsiSelfTest(BaseModel):
    num: int
    description: str
    status: str
    status_verbose: str
    segment_number: int | None = None
    lifetime: int | None = None
    lba_of_first_error: int | None = None
