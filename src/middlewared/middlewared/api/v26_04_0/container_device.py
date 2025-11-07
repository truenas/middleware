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
    'ContainerDeviceDiskChoicesArgs', 'ContainerDeviceDiskChoicesResult', 'ContainerDeviceNicAttachChoicesArgs',
    'ContainerDeviceNicAttachChoicesResult', 'ContainerDeviceUsbDeviceArgs',
    'ContainerDeviceUsbDeviceResult', 'ContainerDeviceUsbChoicesArgs',
    'ContainerDeviceUsbChoicesResult', 'ContainerDevicePciDeviceArgs',
    'ContainerDevicePciDeviceResult', 'ContainerDevicePciDeviceChoicesArgs',
    'ContainerDevicePciDeviceChoicesResult',
]


class ContainerFilesystemDevice(BaseModel):
    dtype: Literal['FILESYSTEM']
    """Device type identifier for FILESYSTEM devices."""
    target: NonEmptyString = Field(pattern=r'^[^{}]*$')
    """Target must not contain braces."""
    source: NonEmptyString = Field(pattern=r'^[^{}]*$')
    """Source must not contain braces, and not start with /mnt/."""


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
    size: int | None = None
    """Size of the disk in bytes. Required if creating a new disk file."""


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
    device: NonEmptyString | None = None
    """Host USB device path to pass through. `null` for controller only."""


# TODO: DISK/PCI/RAW devices are not being added for now
ContainerDeviceType: TypeAlias = Annotated[
    ContainerNICDevice | ContainerFilesystemDevice | ContainerUSBDevice,
    Field(discriminator='dtype')
]


class ContainerDeviceEntry(BaseModel):
    id: int
    """Unique identifier for the containers device."""
    attributes: ContainerDeviceType
    """Device-specific configuration attributes."""
    container: int
    """ID of the container this device belongs to."""


class ContainerDeviceCreate(ContainerDeviceEntry):
    id: Excluded = excluded_field()


@single_argument_args('container_device_create')
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


class ContainerDeviceNicAttachChoicesArgs(BaseModel):
    pass


@single_argument_result
class ContainerDeviceNicAttachChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    """Available network interfaces and bridges for Container NIC attachment."""


class USBCapability(BaseModel):
    product: str | None
    """USB product name. `null` if not available."""
    product_id: str | None
    """USB product identifier. `null` if not available."""
    vendor: str | None
    """USB vendor name. `null` if not available."""
    vendor_id: str | None
    """USB vendor identifier. `null` if not available."""
    bus: str | None
    """USB bus number. `null` if not available."""
    device: str | None
    """USB device number on bus. `null` if not available."""


class ContainerDeviceUsbDeviceArgs(BaseModel):
    device: NonEmptyString
    """USB device identifier to get passthrough information for."""


class USBPassthroughDevice(BaseModel):
    capability: USBCapability
    """USB device capability and identification information."""
    available: bool
    """Whether the USB device is available for passthrough to virtual machines."""
    error: str | None
    """Error message if the device cannot be used for passthrough. `null` if no error."""
    description: str
    """Human-readable description of the USB device."""


class ContainerDeviceUsbDeviceResult(BaseModel):
    result: USBPassthroughDevice
    """Detailed information about the specified USB passthrough device."""


class ContainerDeviceUsbChoicesArgs(BaseModel):
    pass


class ContainerDeviceUsbChoicesResult(BaseModel):
    result: dict[str, USBPassthroughDevice]
    """Object of available USB devices for passthrough with their detailed information."""


class ContainerDevicePciDeviceArgs(BaseModel):
    device: NonEmptyString
    """PCI device identifier to get passthrough information for."""


class ContainerDeviceCapability(BaseModel):
    class_: str | None = Field(alias='class')
    """PCI device class identifier. `null` if not available."""
    domain: str | None
    """PCI domain number. `null` if not available."""
    bus: str | None
    """PCI bus number. `null` if not available."""
    slot: str | None
    """PCI slot number. `null` if not available."""
    function: str | None
    """PCI function number. `null` if not available."""
    product: str | None
    """Product name of the PCI device. `null` if not available."""
    vendor: str | None
    """Vendor name of the PCI device. `null` if not available."""


class ContainerDeviceIOMMUGroupAddress(BaseModel):
    domain: str
    """PCI domain number for this IOMMU group address."""
    bus: str
    """PCI bus number for this IOMMU group address."""
    slot: str
    """PCI slot number for this IOMMU group address."""
    function: str
    """PCI function number for this IOMMU group address."""


class ContainerDeviceIOMMUGroup(BaseModel):
    number: int
    """IOMMU group number for device isolation."""
    addresses: list[ContainerDeviceIOMMUGroupAddress]
    """Array of PCI addresses in this IOMMU group."""


class ContainerDevicePassthroughDevice(BaseModel):
    capability: ContainerDeviceCapability
    """PCI device capability information."""
    controller_type: str | None
    """Type of controller this device provides. `null` if not a controller."""
    iommu_group: ContainerDeviceIOMMUGroup | None = None
    """IOMMU group information for device isolation. `null` if IOMMU not available."""
    available: bool
    """Whether the device is available for passthrough to virtual machines."""
    drivers: list[str]
    """Array of kernel drivers currently bound to this device."""
    error: str | None
    """Error message if the device cannot be used for passthrough. `null` if no error."""
    reset_mechanism_defined: bool
    """Whether the device supports proper reset mechanisms for passthrough."""
    description: str
    """Human-readable description of the PCI device."""
    critical: bool
    """Whether this device is critical to host system operation."""
    device_path: str | None
    """Device filesystem path. `null` if not available."""


class ContainerDevicePciDeviceResult(BaseModel):
    result: ContainerDevicePassthroughDevice
    """Detailed information about the specified PCI passthrough device."""


class ContainerDevicePciDeviceChoicesArgs(BaseModel):
    pass


class ContainerDevicePciDeviceChoicesResult(BaseModel):
    result: dict[str, ContainerDevicePassthroughDevice]
    """Object of available PCI devices for passthrough with their detailed information."""
