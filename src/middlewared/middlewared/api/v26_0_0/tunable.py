from typing import Literal

from middlewared.api.base import BaseModel, ForUpdateMetaclass, Excluded, excluded_field


__all__ = [
    "TunableEntry", "TunableCreateArgs", "TunableCreateResult", "TunableDeleteArgs", "TunableDeleteResult",
    "TunableUpdateArgs", "TunableUpdateResult", "TunableTunableTypeChoicesArgs", "TunableTunableTypeChoicesResult",
]


class TunableCreate(BaseModel):
    type: Literal['SYSCTL', 'UDEV', 'ZFS'] = 'SYSCTL'
    """
    * `SYSCTL`: `var` is a sysctl name (e.g. `kernel.watchdog`) and `value` is its corresponding value (e.g. `0`).
    * `UDEV`: `var` is a udev rules file name (e.g. `10-disable-usb`, `.rules` suffix will be appended automatically) \
    and `value` is its contents (e.g. `BUS=="usb", OPTIONS+="ignore_device"`).
    * `ZFS`: `var` is a ZFS kernel module parameter name (e.g. `zfs_dirty_data_max_max`) and `value` is its value \
    (e.g. `783091712`).
    """
    var: str
    """Name or identifier of the system parameter to tune."""
    value: str
    """Value to assign to the tunable parameter."""
    comment: str = ''
    """Optional descriptive comment explaining the purpose of this tunable."""
    enabled: bool = True
    """Whether this tunable is active and should be applied."""
    update_initramfs: bool = True
    """If `false`, then initramfs will not be updated after creating a ZFS tunable and you will need to run \
    `system boot update_initramfs` manually."""


class TunableEntry(TunableCreate):
    id: int
    """Unique identifier for the tunable configuration."""
    orig_value: str
    """Original system value of the parameter before this tunable was applied."""


class TunableTunableTypeChoices(BaseModel):
    SYSCTL: Literal['SYSCTL']
    """System control parameters that affect kernel behavior."""
    UDEV: Literal['UDEV']
    """Device management rules for hardware detection and configuration."""
    ZFS: Literal['ZFS']
    """ZFS filesystem kernel module parameters."""


class TunableUpdate(TunableCreate, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()
    var: Excluded = excluded_field()


class TunableCreateArgs(BaseModel):
    data: TunableCreate
    """Configuration for creating a new system tunable."""


class TunableCreateResult(BaseModel):
    result: TunableEntry
    """The newly created tunable configuration."""


class TunableDeleteArgs(BaseModel):
    id: int
    """ID of the tunable to delete."""


class TunableDeleteResult(BaseModel):
    result: None
    """Returns `null` on successful tunable deletion."""


class TunableTunableTypeChoicesArgs(BaseModel):
    pass


class TunableTunableTypeChoicesResult(BaseModel):
    result: TunableTunableTypeChoices
    """Available tunable types with their identifiers."""


class TunableUpdateArgs(BaseModel):
    id: int
    """ID of the tunable to update."""
    data: TunableUpdate
    """Updated configuration for the tunable."""


class TunableUpdateResult(BaseModel):
    result: TunableEntry
    """The updated tunable configuration."""
