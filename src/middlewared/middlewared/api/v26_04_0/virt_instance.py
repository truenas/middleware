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
    'VirtInstanceDeviceDeviceUpdateResult', 'VirtInstanceDeviceDeviceDeleteArgs',
    'VirtInstanceDeviceDeviceDeleteResult', 'VirtInstancesMetricsEventSourceArgs',
    'VirtInstancesMetricsEventSourceEvent',
]


# Some popular OS choices
OS_ENUM = Literal['LINUX', 'FREEBSD', 'WINDOWS', 'ARCHLINUX', None]
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
    """Type of IP address (INET for IPv4, INET6 for IPv6)."""
    address: NonEmptyString
    """IP address for the virtual instance."""
    netmask: int | None
    """Network mask in CIDR notation."""


class Image(BaseModel):
    architecture: str | None
    """Hardware architecture of the image (e.g., amd64, arm64)."""
    description: str | None
    """Human-readable description of the image."""
    os: str | None
    """Operating system family of the image."""
    release: str | None
    """Version or release name of the operating system."""
    serial: str | None
    """Unique serial identifier for the image."""
    type: str | None
    """Type of image (container, virtual-machine, etc.)."""
    variant: str | None
    """Image variant (default, cloud, minimal, etc.)."""
    secureboot: bool | None
    """Whether the image supports UEFI Secure Boot."""


class IdmapUserNsEntry(BaseModel):
    hostid: int
    """Starting host ID for the mapping range."""
    maprange: int
    """Number of IDs to map in this range."""
    nsid: int
    """Starting namespace ID for the mapping range."""


class UserNsIdmap(BaseModel):
    uid: IdmapUserNsEntry | None
    """User ID mapping configuration for user namespace isolation."""
    gid: IdmapUserNsEntry | None
    """Group ID mapping configuration for user namespace isolation."""


class VirtInstanceEntry(BaseModel):
    id: str
    """Unique identifier for the virtual instance."""
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    """Human-readable name for the virtual instance."""
    type: InstanceType = 'CONTAINER'
    """Type of virtual instance."""
    status: Literal[
        'RUNNING', 'STOPPED', 'UNKNOWN', 'ERROR', 'FROZEN', 'STARTING', 'STOPPING', 'FREEZING', 'THAWED', 'ABORTING'
    ]
    """Current operational status of the virtual instance."""
    cpu: str | None
    """CPU configuration string or `null` for default allocation."""
    memory: int | None
    """Memory allocation in bytes or `null` for default allocation."""
    autostart: bool
    """Whether the instance automatically starts when the host boots."""
    environment: dict[str, str]
    """Environment variables to set inside the instance."""
    aliases: list[VirtInstanceAlias]
    """Array of IP aliases configured for the instance."""
    image: Image
    """Image information used to create this instance."""
    userns_idmap: UserNsIdmap | None
    """User namespace ID mapping configuration for privilege isolation."""
    raw: Secret[dict | None]
    """Raw low-level configuration options (advanced use only)."""
    vnc_enabled: bool
    """Whether VNC remote access is enabled for the instance."""
    vnc_port: int | None
    """TCP port number for VNC connections or `null` if VNC is disabled."""
    vnc_password: Secret[NonEmptyString | None]
    """Password for VNC access or `null` if no password is set."""
    secure_boot: bool | None
    """Whether UEFI Secure Boot is enabled (VMs only) or `null` for containers."""
    privileged_mode: bool | None
    """Whether the container runs in privileged mode or `null` for VMs."""
    root_disk_size: int | None
    """Size of the root disk in GB or `null` for default size."""
    root_disk_io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI', None]
    """I/O bus type for the root disk or `null` for default."""
    storage_pool: NonEmptyString
    """Storage pool in which the root of the instance is located."""


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
    """Name for the new virtual instance."""
    source_type: Literal['IMAGE'] = 'IMAGE'
    """Source type for instance creation."""
    storage_pool: NonEmptyString | None = None
    """
    Storage pool under which to allocate root filesystem. Must be one of the pools \
    listed in virt.global.config output under "storage_pools". If None (default) then the pool \
    specified in the global configuration will be used.
    """
    image: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    """Image identifier to use for creating the instance."""
    root_disk_size: int = Field(ge=5, default=10)  # In GBs
    """
    This can be specified when creating VMs so the root device's size can be configured. Root device for VMs \
    is a sparse zvol and the field specifies space in GBs and defaults to 10 GBs.
    """
    root_disk_io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI'] = 'NVME'
    """I/O bus type for the root disk (defaults to NVME for best performance)."""
    remote: REMOTE_CHOICES = 'LINUX_CONTAINERS'
    """Remote image source to use."""
    instance_type: Literal['CONTAINER'] = 'CONTAINER'
    """Type of instance to create."""
    environment: dict[ENV_KEY, ENV_VALUE] | None = None
    """Environment variables to set inside the instance."""
    autostart: bool | None = True
    """Whether the instance should automatically start when the host boots."""
    cpu: str | None = None
    """CPU allocation specification or `null` for automatic allocation."""
    devices: list[DeviceType] | None = None
    """Array of devices to attach to the instance."""
    memory: MemoryType | None = None
    """Memory allocation in bytes or `null` for automatic allocation."""
    privileged_mode: bool = False
    """
    This is only valid for containers and should only be set when container instance which is to be deployed is to \
    run in a privileged mode.
    """


class VirtInstanceCreateResult(BaseModel):
    result: VirtInstanceEntry
    """The created virtual instance configuration."""


class VirtInstanceUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    environment: dict[ENV_KEY, ENV_VALUE] | None = None
    """Environment variables to set inside the instance."""
    autostart: bool | None = None
    """Whether the instance should automatically start when the host boots."""
    cpu: str | None = None
    """CPU allocation specification or `null` for automatic allocation."""
    memory: MemoryType | None = None
    """Memory allocation in bytes or `null` for automatic allocation."""
    vnc_port: int | None = Field(ge=5900, le=65535)
    """TCP port number for VNC access (5900-65535) or `null` to disable VNC."""
    enable_vnc: bool
    """Whether to enable VNC remote access for the instance."""
    vnc_password: Secret[NonEmptyString | None]
    """Setting vnc_password to null will unset VNC password."""
    secure_boot: bool
    """Whether to enable UEFI Secure Boot (VMs only)."""
    root_disk_size: int | None = Field(ge=5, default=None)
    """Size of the root disk in GB (minimum 5GB) or `null` to keep current size."""
    root_disk_io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI', None] = None
    """I/O bus type for the root disk or `null` to keep current setting."""
    image_os: str | OS_ENUM = None
    """Operating system type for the instance or `null` for auto-detection."""
    privileged_mode: bool
    """
    This is only valid for containers and should only be set when container instance which is to be deployed is to \
    run in a privileged mode.
    """


class VirtInstanceUpdateArgs(BaseModel):
    id: str
    """ID of the virtual instance to update."""
    virt_instance_update: VirtInstanceUpdate
    """Updated configuration data for the virtual instance."""


class VirtInstanceUpdateResult(BaseModel):
    result: VirtInstanceEntry
    """The updated virtual instance configuration."""


class VirtInstanceDeleteArgs(BaseModel):
    id: str
    """ID of the virtual instance to delete."""


class VirtInstanceDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the virtual instance is successfully deleted."""


class VirtInstanceStartArgs(BaseModel):
    id: str
    """ID of the virtual instance to start."""


class VirtInstanceStartResult(BaseModel):
    result: bool
    """Returns `true` if the instance was successfully started."""


class StopArgs(BaseModel):
    timeout: int = -1
    """Timeout in seconds to wait for graceful shutdown (-1 for no timeout when `force = true`)."""
    force: bool = False
    """Whether to force stop the instance immediately without graceful shutdown."""


class VirtInstanceStopArgs(BaseModel):
    id: str
    """ID of the virtual instance to stop."""
    stop_args: StopArgs = StopArgs()
    """Arguments controlling how the instance is stopped."""

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.stop_args.force is False and self.stop_args.timeout == -1:
            raise ValueError('Timeout should be set if force is disabled')
        return self


class VirtInstanceStopResult(BaseModel):
    result: bool
    """Returns `true` if the instance was successfully stopped."""


class VirtInstanceRestartArgs(VirtInstanceStopArgs):
    pass


class VirtInstanceRestartResult(BaseModel):
    result: bool
    """Returns `true` if the instance was successfully restarted."""


class VirtInstanceImageChoices(BaseModel):
    remote: REMOTE_CHOICES = 'LINUX_CONTAINERS'
    """Remote image source to query for available images."""


class VirtInstanceImageChoicesArgs(BaseModel):
    virt_instances_image_choices: VirtInstanceImageChoices = VirtInstanceImageChoices()
    """Options for filtering available images."""


class ImageChoiceItem(BaseModel):
    label: str
    """Human-readable label for the image."""
    os: str
    """Operating system family of the image."""
    release: str
    """Version or release name of the operating system."""
    archs: list[str]
    """Array of supported hardware architectures."""
    variant: str
    """Image variant (default, cloud, minimal, etc.)."""
    instance_types: list[InstanceType]
    """Array of instance types this image supports."""
    secureboot: bool | None
    """Whether the image supports UEFI Secure Boot or `null` if not applicable."""


class VirtInstanceImageChoicesResult(BaseModel):
    result: dict[str, ImageChoiceItem]
    """Available images indexed by image identifier."""


class VirtInstanceDeviceDeviceListArgs(BaseModel):
    id: str
    """ID of the virtual instance to list devices for."""


class VirtInstanceDeviceDeviceListResult(BaseModel):
    result: list[DeviceType]
    """Array of devices attached to the virtual instance."""


class VirtInstanceDeviceDeviceAddArgs(BaseModel):
    id: str
    """ID of the virtual instance to add device to."""
    device: DeviceType
    """Device configuration to add to the instance."""


class VirtInstanceDeviceDeviceAddResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the device is successfully added."""


class VirtInstanceDeviceDeviceUpdateArgs(BaseModel):
    id: str
    """ID of the virtual instance to update device for."""
    device: DeviceType
    """Updated device configuration."""


class VirtInstanceDeviceDeviceUpdateResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the device is successfully updated."""


class VirtInstanceDeviceDeviceDeleteArgs(BaseModel):
    id: str
    """ID of the virtual instance to remove device from."""
    name: str
    """Name of the device to remove."""


class VirtInstanceDeviceDeviceDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the device is successfully removed."""


class VirtInstancesMetricsEventSourceArgs(BaseModel):
    interval: int = Field(default=2, ge=2)
    """Interval in seconds between metrics updates (minimum 2 seconds)."""


class VirtInstancesMetricsEventSourceEvent(BaseModel):
    result: dict
    """Real-time metrics data for all virtual instances."""
