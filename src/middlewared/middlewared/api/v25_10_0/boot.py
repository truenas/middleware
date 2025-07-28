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
    """Whether to expand the boot pool after attaching the disk."""


class BootGetState(PoolEntry):
    id: Excluded = excluded_field()
    guid: Excluded = excluded_field()


class BootAttachArgs(BaseModel):
    dev: str
    """Device name or path to attach to the boot pool."""
    options: BootAttachOptions = Field(default_factory=BootAttachOptions)
    """Options for the attach operation."""


class BootAttachResult(BaseModel):
    result: None
    """Returns `null` when the disk is successfully attached to the boot pool."""


class BootDetachArgs(BaseModel):
    dev: str
    """Device name or path to detach from the boot pool."""


class BootDetachResult(BaseModel):
    result: None
    """Returns `null` when the disk is successfully detached from the boot pool."""


class BootGetDisksArgs(BaseModel):
    pass


class BootGetDisksResult(BaseModel):
    result: list[str]
    """Array of disk device names that are part of the boot pool."""


class BootGetStateArgs(BaseModel):
    pass


class BootGetStateResult(BaseModel):
    result: BootGetState
    """Current state and configuration of the boot pool."""


class BootReplaceArgs(BaseModel):
    label: str
    """Label of the disk in the boot pool to replace."""
    dev: str
    """Device name or path of the replacement disk."""


class BootReplaceResult(BaseModel):
    result: None
    """Returns `null` when the disk replacement is successfully initiated."""


class BootScrubArgs(BaseModel):
    pass


class BootScrubResult(BaseModel):
    result: None
    """Returns `null` when the boot pool scrub is successfully started."""


class BootSetScrubIntervalArgs(BaseModel):
    interval: PositiveInt
    """Scrub interval in days (must be a positive integer)."""


class BootSetScrubIntervalResult(BaseModel):
    result: PositiveInt
    """The updated scrub interval in days."""
