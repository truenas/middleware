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
    value: str
    comment: str = ''
    enabled: bool = True
    update_initramfs: bool = True
    """If `false`, then initramfs will not be updated after creating a ZFS tunable and you will need to run \
    `system boot update_initramfs` manually."""


class TunableEntry(TunableCreate):
    id: int
    orig_value: str


class TunableTunableTypeChoices(BaseModel):
    SYSCTL: Literal['SYSCTL']
    UDEV: Literal['UDEV']
    ZFS: Literal['ZFS']


class TunableUpdate(TunableCreate, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()
    var: Excluded = excluded_field()


class TunableCreateArgs(BaseModel):
    data: TunableCreate


class TunableCreateResult(BaseModel):
    result: TunableEntry


class TunableDeleteArgs(BaseModel):
    id: int


class TunableDeleteResult(BaseModel):
    result: None


class TunableTunableTypeChoicesArgs(BaseModel):
    pass


class TunableTunableTypeChoicesResult(BaseModel):
    result: TunableTunableTypeChoices


class TunableUpdateArgs(BaseModel):
    id: int
    data: TunableUpdate


class TunableUpdateResult(BaseModel):
    result: TunableEntry
