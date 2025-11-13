from pydantic import ConfigDict, Field
from typing import Annotated, Literal, TypeAlias


from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)


__all__ = [
    'ContainerNICDevice', 'ContainerUSBDevice', 'ContainerDeviceType',
    'ContainerFilesystemDevice', 'ContainerGPUDevice',
    'ContainerDeviceEntry', 'ContainerDeviceCreateArgs', 'ContainerDeviceCreateResult', 'ContainerDeviceUpdateArgs',
    'ContainerDeviceUpdateResult', 'ContainerDeviceDeleteArgs', 'ContainerDeviceDeleteResult',
    'ContainerDeviceDiskChoicesArgs', 'ContainerDeviceDiskChoicesResult', 'ContainerDeviceNicAttachChoicesArgs',
    'ContainerDeviceNicAttachChoicesResult', 'ContainerDeviceUsbChoicesArgs', 'ContainerDeviceUsbChoicesResult',
    'ContainerDeviceGpuChoicesArgs', 'ContainerDeviceGpuChoicesResult',
]


class ContainerFilesystemDevice(BaseModel):
    dtype: Literal['FILESYSTEM']
    """Device type identifier for FILESYSTEM devices."""
    target: NonEmptyString = Field(pattern=r'^[^{}]*$')
    """Target must not contain braces."""
    source: NonEmptyString = Field(pattern=r'^[^{}]*$')
    """Source must not contain braces, and not start with /mnt/."""


class ContainerGPUDevice(BaseModel):
    dtype: Literal['GPU']
    """Device type identifier for GPU devices."""
    gpu_type: Literal['AMD']
    """GPU device type."""
    pci_address: NonEmptyString


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


ContainerDeviceType: TypeAlias = Annotated[
    ContainerFilesystemDevice | ContainerGPUDevice | ContainerNICDevice | ContainerUSBDevice,
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


class USBPassthroughDevice(BaseModel):
    capability: USBCapability
    """USB device capability and identification information."""
    available: bool
    """Whether the USB device is available for passthrough to virtual machines."""
    error: str | None
    """Error message if the device cannot be used for passthrough. `null` if no error."""
    description: str
    """Human-readable description of the USB device."""


class ContainerDeviceUsbChoicesArgs(BaseModel):
    pass


class ContainerDeviceUsbChoicesResult(BaseModel):
    result: dict[str, USBPassthroughDevice]
    """Object of available USB devices for passthrough with their detailed information."""


class ContainerDeviceGpuChoicesArgs(BaseModel):
    pass


class ContainerDeviceGpuChoicesResult(BaseModel):
    result: dict
    """Available GPU(s) for container attachment."""
