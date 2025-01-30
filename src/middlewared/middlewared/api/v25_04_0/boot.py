from typing import Literal

from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel, NotRequired


__all__ = [
    "BootGetDisksArgs", "BootGetDisksResult", "BootAttachArgs", "BootAttachResult", "BootDetachArgs",
    "BootDetachResult", "BootReplaceArgs", "BootReplaceResult", "BootScrubArgs", "BootScrubResult",
    "BootSetScrubIntervalArgs", "BootSetScrubIntervalResult", "BootUpdateInitramfsArgs", "BootUpdateInitramfsResult",
    "BootFormatArgs", "BootFormatResult"
]


class BootAttachOptions(BaseModel):
    expand: bool = False


class BootFormatOptions(BaseModel):
    size: int = NotRequired
    legacy_schema: Literal["BIOS_ONLY", "EFI_ONLY", None] = None


class BootUpdateInitramfsOptions(BaseModel):
    database: str | None = None
    force: bool = False


class BootGetDisksArgs(BaseModel):
    pass


class BootGetDisksResult(BaseModel):
    result: list[str]


class BootAttachArgs(BaseModel):
    dev: str
    options: BootAttachOptions = Field(default_factory=BootAttachOptions)


class BootAttachResult(BaseModel):
    result: None


class BootDetachArgs(BaseModel):
    dev: str


class BootDetachResult(BaseModel):
    result: None


class BootFormatArgs(BaseModel):
    dev: str
    options: BootFormatOptions = Field(default_factory=BootFormatOptions)


class BootFormatResult(BaseModel):
    result: None


class BootReplaceArgs(BaseModel):
    label: str
    dev: str


class BootReplaceResult(BaseModel):
    result: None


class BootScrubArgs(BaseModel):
    pass


class BootScrubResult(BaseModel):
    result: None


class BootSetScrubIntervalArgs(BaseModel):
    interval: PositiveInt


class BootSetScrubIntervalResult(BaseModel):
    result: PositiveInt


class BootUpdateInitramfsArgs(BaseModel):
    options: BootUpdateInitramfsOptions = Field(default_factory=BootUpdateInitramfsOptions)


class BootUpdateInitramfsResult(BaseModel):
    result: bool
