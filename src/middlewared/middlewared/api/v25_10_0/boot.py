from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel


__all__ = [
    "BootGetDisksArgs", "BootGetDisksResult", "BootAttachArgs", "BootAttachResult", "BootDetachArgs",
    "BootDetachResult", "BootReplaceArgs", "BootReplaceResult", "BootScrubArgs", "BootScrubResult",
    "BootSetScrubIntervalArgs", "BootSetScrubIntervalResult",
]


class BootAttachOptions(BaseModel):
    expand: bool = False


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
