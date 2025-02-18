from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel, Excluded, excluded_field
from .pool import PoolEntry


__all__ = [
    "BootGetDisksArgs", "BootGetDisksResult", "BootAttachArgs", "BootAttachResult", "BootDetachArgs",
    "BootDetachResult", "BootReplaceArgs", "BootReplaceResult", "BootScrubArgs", "BootScrubResult",
    "BootSetScrubIntervalArgs", "BootSetScrubIntervalResult", "BootGetStateArgs", "BootGetStateResult",
]


class BootAttachOptions(BaseModel):
    expand: bool = False


class BootGetState(PoolEntry):
    id: Excluded = excluded_field()
    guid: Excluded = excluded_field()


class BootAttachArgs(BaseModel):
    dev: str
    options: BootAttachOptions = Field(default_factory=BootAttachOptions)


class BootAttachResult(BaseModel):
    result: None


class BootDetachArgs(BaseModel):
    dev: str


class BootDetachResult(BaseModel):
    result: None


class BootGetDisksArgs(BaseModel):
    pass


class BootGetDisksResult(BaseModel):
    result: list[str]


class BootGetStateArgs(BaseModel):
    pass


class BootGetStateResult(BaseModel):
    result: BootGetState


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
