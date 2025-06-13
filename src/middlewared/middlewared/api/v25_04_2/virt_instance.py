import os
import re
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field, model_validator, Secret, StringConstraints

from middlewared.api.base import BaseModel, ForUpdateMetaclass, match_validator, NonEmptyString, single_argument_args

from .virt_device import DeviceType, InstanceType


__all__ = [
    'VirtInstanceEntry', 'VirtInstanceCreateArgs', 'VirtInstanceCreateResult', 'VirtInstanceUpdateArgs',
    'VirtInstanceUpdateResult', 'VirtInstanceDeleteArgs', 'VirtInstanceDeleteResult',
    'VirtInstanceStartArgs', 'VirtInstanceStartResult', 'VirtInstanceStopArgs', 'VirtInstanceStopResult',
    'VirtInstanceRestartArgs', 'VirtInstanceRestartResult', 'VirtInstanceImageChoicesArgs',
    'VirtInstanceImageChoicesResult', 'VirtInstanceDeviceDeviceListArgs', 'VirtInstanceDeviceDeviceListResult',
    'VirtInstanceDeviceDeviceAddArgs', 'VirtInstanceDeviceDeviceAddResult', 'VirtInstanceDeviceDeviceUpdateArgs',
    'VirtInstanceDeviceDeviceUpdateResult', 'VirtInstanceDeviceDeviceDeleteArgs', 'VirtInstanceDeviceDeviceDeleteResult',
]


REMOTE_CHOICES: TypeAlias = Literal['LINUX_CONTAINERS']
ENV_KEY: TypeAlias = Annotated[
    str,
    AfterValidator(
        match_validator(
            re.compile(r'^\w[\w/]*$'),
            'ENV_KEY must not be empty, should start with alphanumeric characters'
            ', should not contain whitespaces, and can have _ and /'
        )
    )
]
ENV_VALUE: TypeAlias = Annotated[
    str,
    AfterValidator(
        match_validator(
            re.compile(r'^(?!\s*$).+'),
            'ENV_VALUE must have at least one non-whitespace character to be considered valid'
        )
    )
]


class VirtInstanceAlias(BaseModel):
    type: Literal['INET', 'INET6']
    address: NonEmptyString
    netmask: int | None


class Image(BaseModel):
    architecture: str | None
    description: str | None
    os: str | None
    release: str | None
    serial: str | None
    type: str | None
    variant: str | None
    secureboot: bool | None


class IdmapUserNsEntry(BaseModel):
    hostid: int
    maprange: int
    nsid: int


class UserNsIdmap(BaseModel):
    uid: IdmapUserNsEntry
    gid: IdmapUserNsEntry


class VirtInstanceEntry(BaseModel):
    id: str
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    type: InstanceType = 'CONTAINER'
    status: Literal['RUNNING', 'STOPPED', 'UNKNOWN', 'ERROR', 'FROZEN', 'STARTING', 'STOPPING', 'FREEZING', 'THAWED', 'ABORTING']
    cpu: str | None
    memory: int | None
    autostart: bool
    environment: dict[str, str]
    aliases: list[VirtInstanceAlias]
    image: Image
    userns_idmap: UserNsIdmap | None
    raw: Secret[dict | None]
    vnc_enabled: bool
    vnc_port: int | None
    vnc_password: Secret[NonEmptyString | None]
    secure_boot: bool | None
    root_disk_size: int | None
    root_disk_io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI', None]
    storage_pool: NonEmptyString
    "Storage pool in which the root of the instance is located."


def validate_memory(value: int) -> int:
    if value < 33554432:
        raise ValueError('Value must be 32MiB or larger')
    return value


# Lets require at least 32MiB of reserved memory
# This value is somewhat arbitrary but hard to think lower value would have to be used
# (would most likely be a typo).
# Running container with very low memory will probably cause it to be killed by the cgroup OOM
MemoryType: TypeAlias = Annotated[int, AfterValidator(validate_memory)]


@single_argument_args('virt_instance_create')
class VirtInstanceCreateArgs(BaseModel):
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    iso_volume: NonEmptyString | None = None
    source_type: Literal[None, 'IMAGE', 'ZVOL', 'ISO', 'VOLUME'] = 'IMAGE'
    storage_pool: NonEmptyString | None = None
    '''
    Storage pool under which to allocate root filesystem. Must be one of the pools
    listed in virt.global.config output under "storage_pools". If None (default) then the pool
    specified in the global configuration will be used.
    '''
    image: Annotated[NonEmptyString, StringConstraints(max_length=200)] | None = None
    root_disk_size: int = Field(ge=5, default=10)  # In GBs
    '''
    This can be specified when creating VMs so the root device's size can be configured. Root device for VMs
    is a sparse zvol and the field specifies space in GBs and defaults to 10 GBs.
    '''
    root_disk_io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI'] = 'NVME'
    remote: REMOTE_CHOICES = 'LINUX_CONTAINERS'
    instance_type: InstanceType = 'CONTAINER'
    environment: dict[ENV_KEY, ENV_VALUE] | None = None
    autostart: bool | None = True
    cpu: str | None = None
    devices: list[DeviceType] | None = None
    memory: MemoryType | None = None
    secure_boot: bool = False
    enable_vnc: bool = False
    vnc_port: int | None = Field(ge=5900, le=65535, default=None)
    zvol_path: NonEmptyString | None = None
    '''
    This is useful when a VM wants to be booted where a ZVOL already has a VM bootstrapped in it and needs
    to be ported over to virt plugin. Virt will consume this zvol and add it as a DISK device to the instance
    with boot priority set to 1 so the VM can be booted from it.
    '''
    volume: NonEmptyString | None = None
    '''
    This should be set when source type is "VOLUME" and should be the name of the virt volume which should
    be used to boot the VM instance.
    '''
    vnc_password: Secret[NonEmptyString | None] = None

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.instance_type == 'CONTAINER':
            if self.source_type != 'IMAGE':
                raise ValueError('Source type must be set to "IMAGE" when instance type is CONTAINER')
            if self.enable_vnc:
                raise ValueError('VNC is not supported for containers and `enable_vnc` should be unset')
            if self.zvol_path:
                raise ValueError('Zvol path is only supported for VMs')
        else:
            if self.enable_vnc and self.vnc_port is None:
                raise ValueError('VNC port must be set when VNC is enabled')

            if self.vnc_password is not None and not self.enable_vnc:
                raise ValueError('VNC password can only be set when VNC is enabled')

            if self.source_type == 'ISO' and self.iso_volume is None:
                raise ValueError('ISO volume must be set when source type is "ISO"')

            if self.source_type == 'VOLUME' and self.volume is None:
                raise ValueError('volume must be set when source type is "VOLUME"')

            if self.source_type == 'ZVOL':
                if self.zvol_path is None:
                    raise ValueError('Zvol path must be set when source type is "ZVOL"')
                if self.zvol_path.startswith('/dev/zvol/') is False:
                    raise ValueError('Zvol path must be a valid zvol path')
                elif not os.path.exists(self.zvol_path):
                    raise ValueError(f'Zvol path {self.zvol_path} does not exist')

        if self.source_type == 'IMAGE' and self.image is None:
            raise ValueError('Image must be set when source type is "IMAGE"')
        elif self.source_type != 'IMAGE' and self.image:
            raise ValueError('Image must not be set when source type is not "IMAGE"')

        return self


class VirtInstanceCreateResult(BaseModel):
    result: VirtInstanceEntry


class VirtInstanceUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    environment: dict[ENV_KEY, ENV_VALUE] | None = None
    autostart: bool | None = None
    cpu: str | None = None
    memory: MemoryType | None = None
    vnc_port: int | None = Field(ge=5900, le=65535)
    enable_vnc: bool
    vnc_password: Secret[NonEmptyString | None]
    '''Setting vnc_password to null will unset VNC password'''
    secure_boot: bool = False
    root_disk_size: int | None = Field(ge=5, default=None)
    root_disk_io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI', None] = None


class VirtInstanceUpdateArgs(BaseModel):
    id: str
    virt_instance_update: VirtInstanceUpdate


class VirtInstanceUpdateResult(BaseModel):
    result: VirtInstanceEntry


class VirtInstanceDeleteArgs(BaseModel):
    id: str


class VirtInstanceDeleteResult(BaseModel):
    result: Literal[True]


class VirtInstanceStartArgs(BaseModel):
    id: str


class VirtInstanceStartResult(BaseModel):
    result: bool


class StopArgs(BaseModel):
    timeout: int = -1
    force: bool = False


class VirtInstanceStopArgs(BaseModel):
    id: str
    stop_args: StopArgs = StopArgs()

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.stop_args.force is False and self.stop_args.timeout == -1:
            raise ValueError('Timeout should be set if force is disabled')
        return self


class VirtInstanceStopResult(BaseModel):
    result: bool


class VirtInstanceRestartArgs(VirtInstanceStopArgs):
    pass


class VirtInstanceRestartResult(BaseModel):
    result: bool


class VirtInstanceImageChoices(BaseModel):
    remote: REMOTE_CHOICES = 'LINUX_CONTAINERS'


class VirtInstanceImageChoicesArgs(BaseModel):
    virt_instances_image_choices: VirtInstanceImageChoices = VirtInstanceImageChoices()


class ImageChoiceItem(BaseModel):
    label: str
    os: str
    release: str
    archs: list[str]
    variant: str
    instance_types: list[InstanceType]
    secureboot: bool | None


class VirtInstanceImageChoicesResult(BaseModel):
    result: dict[str, ImageChoiceItem]


class VirtInstanceDeviceDeviceListArgs(BaseModel):
    id: str


class VirtInstanceDeviceDeviceListResult(BaseModel):
    result: list[DeviceType]


class VirtInstanceDeviceDeviceAddArgs(BaseModel):
    id: str
    device: DeviceType


class VirtInstanceDeviceDeviceAddResult(BaseModel):
    result: Literal[True]


class VirtInstanceDeviceDeviceUpdateArgs(BaseModel):
    id: str
    device: DeviceType


class VirtInstanceDeviceDeviceUpdateResult(BaseModel):
    result: Literal[True]


class VirtInstanceDeviceDeviceDeleteArgs(BaseModel):
    id: str
    name: str


class VirtInstanceDeviceDeviceDeleteResult(BaseModel):
    result: Literal[True]
