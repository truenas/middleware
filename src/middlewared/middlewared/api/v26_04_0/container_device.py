from pydantic import ConfigDict, Field, model_validator
from typing import Annotated, Literal, TypeAlias


from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)


__all__ = [
    'ContainerNICDevice', 'ContainerPCIDevice', 'ContainerRAWDevice',
    'ContainerDiskDevice', 'ContainerUSBDevice', 'ContainerDeviceType', 'ContainerFilesystemDevice',
    'ContainerDeviceEntry', 'ContainerDeviceCreateArgs', 'ContainerDeviceCreateResult', 'ContainerDeviceUpdateArgs',
    'ContainerDeviceUpdateResult', 'ContainerDeviceDeleteArgs', 'ContainerDeviceDeleteResult',
    'ContainerDeviceDiskChoicesArgs', 'ContainerDeviceDiskChoicesResult', 'ContainerDeviceIotypeChoicesArgs',
    'ContainerDeviceIotypeChoicesResult', 'ContainerDeviceNicAttachChoicesArgs',
    'ContainerDeviceNicAttachChoicesResult'
]


class ContainerFilesystemDevice(BaseModel):
    dtype: Literal['FILESYSTEM']
    """Device type identifier for FILESYSTEM devices."""
    target: NonEmptyString = Field(pattern=r'^[^{}]*$')
    """target must not contain "{", "}" characters"""
    source: NonEmptyString = Field(pattern=r'^[^{}]*$')
    """source must not contain "{", "}" characters, and it should start with "/mnt/"."""


class ContainerNICDevice(BaseModel):
    dtype: Literal['NIC']
    """Device type identifier for network interface cards."""
    trust_guest_rx_filters: bool = False
    """Whether to trust guest OS receive filter settings for better performance."""
    type_: Literal['E1000', 'VIRTIO'] = Field(alias='type', default='E1000')
    """Network interface controller type. `E1000` for Intel compatibility, `VIRTIO` for performance."""
    nic_attach: str | None = None
    """Host network interface or bridge to attach to. `null` for no attachment."""
    mac: str | None = Field(default=None, pattern='^([0-9A-Fa-f]{2}[:-]?){5}([0-9A-Fa-f]{2})$')
    """MAC address for the virtual network interface. `null` for auto-generation."""


class ContainerPCIDevice(BaseModel):
    dtype: Literal['PCI']
    """Device type identifier for PCI passthrough devices."""
    pptdev: NonEmptyString
    """Host PCI device identifier to pass through to the container."""


class ContainerRAWDevice(BaseModel):
    dtype: Literal['RAW']
    """Device type identifier for raw disk devices."""
    path: NonEmptyString = Field(pattern='^[^{}]*$', description='Path must not contain "{", "}" characters.')
    """Filesystem path to the raw disk device or image file."""
    type_: Literal['AHCI', 'VIRTIO'] = Field(alias='type', default='AHCI')
    """Disk controller interface type. AHCI for compatibility, VIRTIO for performance."""
    exists: bool = False
    """Whether the disk file already exists or should be created."""
    boot: bool = False
    """Whether this disk should be marked as bootable."""
    size: int | None = None
    """Size of the disk in bytes. Required if creating a new disk file."""
    logical_sectorsize: Literal[None, 512, 4096] | None = None
    """Logical sector size for the disk. `null` for default."""
    physical_sectorsize: Literal[None, 512, 4096] | None = None
    """Physical sector size for the disk. `null` for default."""
    iotype: Literal['NATIVE', 'THREADS', 'IO_URING'] = 'THREADS'
    """I/O backend type for disk operations."""
    serial: NonEmptyString | None = None
    """Serial number to assign to the virtual disk. `null` for auto-generated."""


class ContainerDiskDevice(BaseModel):
    dtype: Literal['DISK']
    """Device type identifier for virtual disk devices."""
    path: NonEmptyString | None = None
    """Path to existing disk file or ZFS volume. `null` if creating a new ZFS volume."""
    type_: Literal['AHCI', 'VIRTIO'] = Field(alias='type', default='AHCI')
    """Disk controller interface type. AHCI for compatibility, VIRTIO for performance."""
    create_zvol: bool = False
    """Whether to create a new ZFS volume for this disk."""
    zvol_name: str | None = None
    """Name for the new ZFS volume. Required if `create_zvol` is true."""
    zvol_volsize: int | None = None
    """Size of the new ZFS volume in bytes. Required if `create_zvol` is true."""
    logical_sectorsize: Literal[None, 512, 4096] | None = None
    """Logical sector size for the disk. `null` for default."""
    physical_sectorsize: Literal[None, 512, 4096] | None = None
    """Physical sector size for the disk. `null` for default."""
    iotype: Literal['NATIVE', 'THREADS', 'IO_URING'] = 'THREADS'
    """I/O backend type for disk operations."""
    serial: NonEmptyString | None = None
    """Serial number to assign to the virtual disk. `null` for auto-generated."""

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.path is not None and self.create_zvol is True:
            raise ValueError('Path should not be provided if create_zvol is set')
        if self.path is None and self.create_zvol is None:
            raise ValueError('Either `path` or `create_zvol` should be set')
        if self.path is None and self.create_zvol is False:
            raise ValueError('Path must be specified if create_zvol is not set')

        return self


class USBAttributes(BaseModel):
    vendor_id: NonEmptyString = Field(pattern='^0x.*')
    """USB vendor identifier in hexadecimal format (e.g., '0x1d6b' for Linux Foundation)."""
    product_id: NonEmptyString = Field(pattern='^0x.*')
    """USB product identifier in hexadecimal format (e.g., '0x0002' for 2.0 root hub)."""


class ContainerUSBDevice(BaseModel):
    dtype: Literal['USB']
    """Device type identifier for USB devices."""
    usb: USBAttributes | None = None
    """USB device attributes for identification. `null` for USB host controller only."""
    controller_type: Literal[
        'piix3-uhci', 'piix4-uhci', 'ehci', 'ich9-ehci1',
        'vt82c686b-uhci', 'pci-ohci', 'nec-xhci'
    ] = 'nec-xhci'
    """USB controller type for the virtual machine."""
    device: NonEmptyString | None = None
    """Host USB device path to pass through. `null` for controller only."""


# ContainerUSBDevice / ContainerPCIDevice
# TODO: Let's please add support for these after testing thoroughly these devices subsequently.
ContainerDeviceType: TypeAlias = Annotated[
    ContainerNICDevice | ContainerRAWDevice | ContainerDiskDevice | ContainerFilesystemDevice,
    Field(discriminator='dtype')
]


class ContainerDeviceEntry(BaseModel):
    id: int
    """Unique identifier for the containers device."""
    attributes: ContainerDeviceType
    """Device-specific configuration attributes."""
    container: int
    """ID of the container this device belongs to."""
    order: int | None = None  # FIXME: This needs to be fixed for both vms/containers
    """Boot order priority for this device (lower numbers boot first)."""


class ContainerDeviceCreate(ContainerDeviceEntry):
    order: int | None = None
    """Boot order priority for this device. `null` for automatic assignment."""
    id: Excluded = excluded_field()


@single_argument_args('vm_device_create')
class ContainerDeviceCreateArgs(ContainerDeviceCreate):
    pass


class ContainerDeviceCreateResult(BaseModel):
    result: ContainerDeviceEntry
    """The newly created container device configuration."""


class ContainerDeviceUpdate(ContainerDeviceCreate, metaclass=ForUpdateMetaclass):
    # This will still get validated when update itself is called based off how we have
    # logic to validate different device types
    attributes: dict


class ContainerDeviceUpdateArgs(BaseModel):
    id: int
    """ID of the container device to update."""
    container_device_update: ContainerDeviceUpdate
    """Updated configuration for the container device."""


class ContainerDeviceUpdateResult(BaseModel):
    result: ContainerDeviceEntry
    """The updated container device configuration."""


class ContainerDeviceDeleteOptions(BaseModel):
    force: bool = False
    """Force deletion even if the device is in use."""
    raw_file: bool = False
    """Delete the underlying raw disk file when removing the device."""
    zvol: bool = False
    """Delete the underlying ZFS volume when removing the device."""


class ContainerDeviceDeleteArgs(BaseModel):
    id: int
    """ID of the container device to delete."""
    options: ContainerDeviceDeleteOptions = ContainerDeviceDeleteOptions()
    """Options controlling the device deletion process."""


class ContainerDeviceDeleteResult(BaseModel):
    result: bool
    """Whether the container device was successfully deleted."""


class ContainerDeviceDiskChoicesArgs(BaseModel):
    pass


class ContainerDeviceDiskChoices(BaseModel):
    model_config = ConfigDict(extra='allow')


class ContainerDeviceDiskChoicesResult(BaseModel):
    result: ContainerDeviceDiskChoices
    """Available disk devices and storage volumes for container attachment."""


class ContainerDeviceIotypeChoicesArgs(BaseModel):
    pass


@single_argument_result
class ContainerDeviceIotypeChoicesResult(BaseModel):
    NATIVE: str = 'NATIVE'
    """Native asynchronous I/O for best performance with NVME."""
    THREADS: str = 'THREADS'
    """Thread-based I/O suitable for most storage types."""
    IO_URING: str = 'IO_URING'
    """Linux io_uring interface for high-performance async I/O."""


class ContainerDeviceNicAttachChoicesArgs(BaseModel):
    pass


@single_argument_result
class ContainerDeviceNicAttachChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    """Available network interfaces and bridges for Container NIC attachment."""
