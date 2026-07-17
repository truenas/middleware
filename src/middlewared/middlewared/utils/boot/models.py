from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel

# NOTE: These models back `private=True` api_methods (`boot.format`, `boot.update_initramfs`).
# `check_model_module` requires private-method models to live OUTSIDE `middlewared.api.*`, so they
# are defined here rather than in `api/v27_0_0/`. They live under `utils/boot/` (not the `boot`
# plugin package) so consumers can import them without triggering the plugin's heavy `__init__`.

__all__ = (
    "BootFormatOptions",
    "BootFormatArgs",
    "BootFormatResult",
    "BootUpdateInitramfsOptions",
    "BootUpdateInitramfsArgs",
    "BootUpdateInitramfsResult",
)


class BootFormatOptions(BaseModel):
    size: int | None = Field(
        default=None,
        description="Size in bytes of the ZFS data partition. When `null`, the partition consumes the remaining space.",
    )
    legacy_schema: Literal["BIOS_ONLY", "EFI_ONLY", None] = Field(
        default=None,
        description="Legacy partition layout to reproduce on an existing disk, or `null` for the modern layout.",
    )


class BootFormatArgs(BaseModel):
    dev: str = Field(description="Device name to format.")
    options: BootFormatOptions = Field(
        default_factory=BootFormatOptions, description="Options for the format operation."
    )


class BootFormatResult(BaseModel):
    result: None = Field(description="Returns `null` when the device is successfully formatted.")


class BootUpdateInitramfsOptions(BaseModel):
    force: bool = Field(
        default=False, description="When `true`, force a rebuild of the initramfs even if nothing changed."
    )


class BootUpdateInitramfsArgs(BaseModel):
    options: BootUpdateInitramfsOptions = Field(
        default_factory=BootUpdateInitramfsOptions,
        description="Options for the initramfs update.",
    )


class BootUpdateInitramfsResult(BaseModel):
    result: bool = Field(description="`true` if the initramfs was updated, `false` otherwise.")
