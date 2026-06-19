from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel, Excluded, excluded_field

from .pool import PoolEntry

__all__ = [
    "BootGetDisksArgs", "BootGetDisksResult", "BootAttachArgs", "BootAttachResult", "BootDetachArgs",
    "BootDetachResult", "BootReplaceArgs", "BootReplaceResult", "BootScrubArgs", "BootScrubResult",
    "BootSetScrubIntervalArgs", "BootSetScrubIntervalResult", "BootGetStateArgs", "BootGetStateResult",
]


class BootAttachOptions(BaseModel):
    expand: bool = Field(
        default=False,
        description=(
            "When `true`, size the new disk's partition to the maximum available space. When `false`, size it to "
            "match the existing boot pool partition to avoid a size mismatch if a disk later fails."
        ),
    )


class BootGetState(PoolEntry):
    id: Excluded = excluded_field()
    guid: Excluded = excluded_field()


class BootAttachArgs(BaseModel):
    dev: str = Field(description="Device name or path to attach to the boot pool.")
    options: BootAttachOptions = Field(
        default_factory=BootAttachOptions,
        description="Options for the attach operation.",
    )


class BootAttachResult(BaseModel):
    result: None = Field(description="Returns `null` when the disk is successfully attached to the boot pool.")


class BootDetachArgs(BaseModel):
    dev: str = Field(description="Device name or path to detach from the boot pool.")


class BootDetachResult(BaseModel):
    result: None = Field(description="Returns `null` when the disk is successfully detached from the boot pool.")


class BootGetDisksArgs(BaseModel):
    pass


class BootGetDisksResult(BaseModel):
    result: list[str] = Field(description="Array of disk device names that are part of the boot pool.")


class BootGetStateArgs(BaseModel):
    pass


class BootGetStateResult(BaseModel):
    result: BootGetState = Field(description="Current state and configuration of the boot pool.")


class BootReplaceArgs(BaseModel):
    label: str = Field(description="Label of the disk in the boot pool to replace.")
    dev: str = Field(description="Device name or path of the replacement disk.")


class BootReplaceResult(BaseModel):
    result: None = Field(description="Returns `null` when the disk replacement is successfully initiated.")


class BootScrubArgs(BaseModel):
    pass


class BootScrubResult(BaseModel):
    result: None = Field(description="Returns `null` when the boot pool scrub is successfully started.")


class BootSetScrubIntervalArgs(BaseModel):
    interval: PositiveInt = Field(description="Scrub interval in days (must be a positive integer).")


class BootSetScrubIntervalResult(BaseModel):
    result: PositiveInt = Field(description="The updated scrub interval in days.")
