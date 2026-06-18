from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Discriminator, Field, model_validator, RootModel, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)


__all__ = [
    'VMCDROMDevice', 'VMDisplayDevice', 'VMNICDevice', 'VMPCIDevice', 'VMRAWDevice', 'VMDiskDevice', 'VMUSBDevice',
    'VMDeviceType', 'VMDeviceEntry', 'VMDeviceCreateArgs', 'VMDeviceCreateResult', 'VMDeviceUpdateArgs',
    'VMDeviceUpdateResult', 'VMDeviceDeleteArgs', 'VMDeviceDeleteResult', 'VMDeviceDiskChoicesArgs',
    'VMDeviceDiskChoicesResult', 'VMDeviceIotypeChoicesArgs', 'VMDeviceIotypeChoicesResult',
    'VMDeviceNicAttachChoicesArgs',
    'VMDeviceNicAttachChoicesResult', 'VMDeviceBindChoicesArgs', 'VMDeviceBindChoicesResult',
    'VMDevicePassthroughDeviceArgs', 'VMDevicePassthroughDeviceResult', 'VMDeviceIommuEnabledArgs',
    'VMDeviceIommuEnabledResult', 'VMDevicePassthroughDeviceChoicesArgs', 'VMDevicePassthroughDeviceChoicesResult',
    'VMDevicePptdevChoicesArgs', 'VMDevicePptdevChoicesResult',
    'VMDeviceUsbPassthroughDeviceArgs', 'VMDeviceUsbPassthroughDeviceResult',
    'VMDeviceUsbPassthroughChoicesArgs', 'VMDeviceUsbPassthroughChoicesResult',
    'VMDeviceUsbControllerChoicesArgs', 'VMDeviceUsbControllerChoicesResult',
    'VMDeviceConvertArgs', 'VMDeviceConvertResult',
    'VMDeviceVirtualSizeArgs', 'VMDeviceVirtualSizeResult'
]


class VMCDROMDevice(BaseModel):
    dtype: Literal['CDROM'] = Field(description="Device type identifier for CD-ROM/DVD devices.")
    path: NonEmptyString = Field(
        pattern=r'^[^{}]*$',
        description="Path must not contain \"{\", \"}\" characters, and it should start with \"/mnt/\".",
    )


class VMDisplayDevice(BaseModel):
    dtype: Literal['DISPLAY'] = Field(description="Device type identifier for display/graphics devices.")
    resolution: Literal[
        '1920x1200', '1920x1080', '1600x1200', '1600x900',
        '1400x1050', '1280x1024', '1280x720',
        '1024x768', '800x600', '640x480',
    ] = Field(default='1024x768', description="Screen resolution for the virtual display.")
    port: int | None = Field(
        default=None,
        ge=5900,
        le=65535,
        description="VNC/SPICE port number for remote display access. `null` for auto-assignment.",
    )
    web_port: int | None = Field(
        default=None,
        description="Web-based display access port number. `null` for auto-assignment.",
    )
    bind: NonEmptyString = Field(default='127.0.0.1', description="IP address to bind the display server to.")
    wait: bool = Field(default=False, description="Whether to wait for a client connection before starting the VM.")
    password: Secret[str | None] = Field(default=None, description="Password for display server authentication.")
    web: bool = Field(default=True, description="Whether to enable web-based display access.")
    type_: Literal['SPICE', 'VNC'] = Field(alias='type', default='SPICE', description="Display protocol type.")


class VMNICDevice(BaseModel):
    dtype: Literal['NIC'] = Field(description="Device type identifier for network interface cards.")
    trust_guest_rx_filters: bool = Field(
        default=False,
        description="Whether to trust guest OS receive filter settings for better performance.",
    )
    type_: Literal['E1000', 'VIRTIO'] = Field(
        alias='type',
        default='E1000',
        description="Network interface controller type. `E1000` for Intel compatibility, `VIRTIO` for performance.",
    )
    nic_attach: str | None = Field(
        default=None,
        description="Host network interface or bridge to attach to. `null` for no attachment.",
    )
    mac: str | None = Field(
        default=None,
        pattern='^([0-9A-Fa-f]{2}[:-]?){5}([0-9A-Fa-f]{2})$',
        description="MAC address for the virtual network interface. `null` for auto-generation.",
    )


class VMPCIDevice(BaseModel):
    dtype: Literal['PCI'] = Field(description="Device type identifier for PCI passthrough devices.")
    pptdev: NonEmptyString = Field(description="Host PCI device identifier to pass through to the VM.")


class VMRAWDevice(BaseModel):
    dtype: Literal['RAW'] = Field(description="Device type identifier for raw disk devices.")
    path: NonEmptyString = Field(
        pattern='^[^{}]*$',
        description="Filesystem path to the raw disk device or image file.",
    )
    type_: Literal['AHCI', 'VIRTIO'] = Field(
        alias='type',
        default='AHCI',
        description="Disk controller interface type. AHCI for compatibility, VIRTIO for performance.",
    )
    exists: bool = Field(default=False, description="Whether the disk file already exists or should be created.")
    boot: bool = Field(default=False, description="Whether this disk should be marked as bootable.")
    size: int | None = Field(
        default=None,
        description="Size of the disk in bytes. Required if creating a new disk file.",
    )
    logical_sectorsize: Literal[None, 512, 4096] | None = Field(
        default=None,
        description="Logical sector size for the disk. `null` for default.",
    )
    physical_sectorsize: Literal[None, 512, 4096] | None = Field(
        default=None,
        description="Physical sector size for the disk. `null` for default.",
    )
    iotype: Literal['NATIVE', 'THREADS', 'IO_URING'] = Field(
        default='THREADS',
        description="I/O backend type for disk operations.",
    )
    serial: NonEmptyString | None = Field(
        default=None,
        description="Serial number to assign to the virtual disk. `null` for auto-generated.",
    )


class VMDiskDevice(BaseModel):
    dtype: Literal['DISK'] = Field(description="Device type identifier for virtual disk devices.")
    path: NonEmptyString | None = Field(
        default=None,
        description="Path to existing disk file or ZFS volume. `null` if creating a new ZFS volume.",
    )
    type_: Literal['AHCI', 'VIRTIO'] = Field(
        alias='type',
        default='AHCI',
        description="Disk controller interface type. AHCI for compatibility, VIRTIO for performance.",
    )
    create_zvol: bool = Field(default=False, description="Whether to create a new ZFS volume for this disk.")
    zvol_name: str | None = Field(
        default=None,
        description="Name for the new ZFS volume. Required if `create_zvol` is true.",
    )
    zvol_volsize: int | None = Field(
        default=None,
        description="Size of the new ZFS volume in bytes. Required if `create_zvol` is true.",
    )
    logical_sectorsize: Literal[None, 512, 4096] | None = Field(
        default=None,
        description="Logical sector size for the disk. `null` for default.",
    )
    physical_sectorsize: Literal[None, 512, 4096] | None = Field(
        default=None,
        description="Physical sector size for the disk. `null` for default.",
    )
    iotype: Literal['NATIVE', 'THREADS', 'IO_URING'] = Field(
        default='THREADS',
        description="I/O backend type for disk operations.",
    )
    serial: NonEmptyString | None = Field(
        default=None,
        description="Serial number to assign to the virtual disk. `null` for auto-generated.",
    )

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
    vendor_id: NonEmptyString = Field(
        pattern='^0x.*',
        description="USB vendor identifier in hexadecimal format (e.g., '0x1d6b' for Linux Foundation).",
    )
    product_id: NonEmptyString = Field(
        pattern='^0x.*',
        description="USB product identifier in hexadecimal format (e.g., '0x0002' for 2.0 root hub).",
    )


class VMUSBDevice(BaseModel):
    dtype: Literal['USB'] = Field(description="Device type identifier for USB devices.")
    usb: USBAttributes | None = Field(
        default=None,
        description="USB device attributes for identification. `null` for USB host controller only.",
    )
    controller_type: Literal[
        'piix3-uhci', 'piix4-uhci', 'ehci', 'ich9-ehci1',
        'vt82c686b-uhci', 'pci-ohci', 'nec-xhci', 'qemu-xhci',
    ] = Field(default='nec-xhci', description="USB controller type for the virtual machine.")
    device: NonEmptyString | None = Field(
        default=None,
        description="Host USB device path to pass through. `null` for controller only.",
    )


VMDeviceType: TypeAlias = Annotated[
    VMCDROMDevice | VMDisplayDevice | VMNICDevice | VMPCIDevice | VMRAWDevice | VMDiskDevice | VMUSBDevice,
    Discriminator('dtype')
]


# VM Device Service models


class VMDeviceEntry(BaseModel):
    id: int = Field(description="Unique identifier for the VM device.")
    attributes: VMDeviceType = Field(description="Device-specific configuration attributes.")
    vm: int = Field(description="ID of the virtual machine this device belongs to.")
    order: int = Field(description="Boot order priority for this device (lower numbers boot first).")


class VMDeviceCreate(VMDeviceEntry):
    order: int | None = Field(
        default=None,
        description="Boot order priority for this device. `null` for automatic assignment.",
    )
    id: Excluded = excluded_field()


@single_argument_args('vm_device_create')
class VMDeviceCreateArgs(VMDeviceCreate):
    pass


class VMDeviceCreateResult(BaseModel):
    result: VMDeviceEntry = Field(description="The newly created VM device configuration.")


class VMDeviceUpdate(VMDeviceCreate, metaclass=ForUpdateMetaclass):
    # This will still get validated when update itself is called based off how we have
    # logic to validate different device types
    attributes: dict


class VMDeviceUpdateArgs(BaseModel):
    id: int = Field(description="ID of the VM device to update.")
    vm_device_update: VMDeviceUpdate = Field(description="Updated configuration for the VM device.")


class VMDeviceUpdateResult(BaseModel):
    result: VMDeviceEntry = Field(description="The updated VM device configuration.")


class VMDeviceDeleteOptions(BaseModel):
    force: bool = Field(default=False, description="Force deletion even if the device is in use.")
    raw_file: bool = Field(default=False, description="Delete the underlying raw disk file when removing the device.")
    zvol: bool = Field(default=False, description="Delete the underlying ZFS volume when removing the device.")


class VMDeviceDeleteArgs(BaseModel):
    id: int = Field(description="ID of the VM device to delete.")
    options: VMDeviceDeleteOptions = Field(
        default=VMDeviceDeleteOptions(),
        description="Options controlling the device deletion process.",
    )


class VMDeviceDeleteResult(BaseModel):
    result: bool = Field(description="Whether the VM device was successfully deleted.")


class VMDeviceDiskChoicesArgs(BaseModel):
    pass


class VMDeviceDiskChoices(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMDeviceDiskChoicesResult(BaseModel):
    result: VMDeviceDiskChoices = Field(description="Available disk devices and storage volumes for VM attachment.")


class VMDeviceIotypeChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceIotypeChoicesResult(BaseModel):
    NATIVE: str = Field(default='NATIVE', description="Native asynchronous I/O for best performance with NVMe.")
    THREADS: str = Field(default='THREADS', description="Thread-based I/O suitable for most storage types.")
    IO_URING: str = Field(default='IO_URING', description="Linux io_uring interface for high-performance async I/O.")


class VMDeviceNicAttachChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceNicAttachChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    """Available network interfaces and bridges for VM NIC attachment."""


class VMDeviceBindChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceBindChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    """Available IP addresses for VM display server binding."""


class VMDeviceIommuEnabledArgs(BaseModel):
    pass


class VMDeviceIommuEnabledResult(BaseModel):
    result: bool = Field(description="Whether IOMMU (Input-Output Memory Management Unit) is enabled on the system.")


class VMDevicePassthroughDeviceArgs(BaseModel):
    device: NonEmptyString = Field(description="PCI device identifier to get passthrough information for.")


class VMDeviceCapability(BaseModel):
    class_: str | None = Field(alias='class', description="PCI device class identifier. `null` if not available.")
    domain: str | None = Field(description="PCI domain number. `null` if not available.")
    bus: str | None = Field(description="PCI bus number. `null` if not available.")
    slot: str | None = Field(description="PCI slot number. `null` if not available.")
    function: str | None = Field(description="PCI function number. `null` if not available.")
    product: str | None = Field(description="Product name of the PCI device. `null` if not available.")
    vendor: str | None = Field(description="Vendor name of the PCI device. `null` if not available.")


class VMDeviceIOMMUGroupAddress(BaseModel):
    domain: str = Field(description="PCI domain number for this IOMMU group address.")
    bus: str = Field(description="PCI bus number for this IOMMU group address.")
    slot: str = Field(description="PCI slot number for this IOMMU group address.")
    function: str = Field(description="PCI function number for this IOMMU group address.")


class VMDeviceIOMMUGroup(BaseModel):
    number: int = Field(description="IOMMU group number for device isolation.")
    addresses: list[VMDeviceIOMMUGroupAddress] = Field(description="Array of PCI addresses in this IOMMU group.")


class VMDevicePassthroughDevice(BaseModel):
    capability: VMDeviceCapability = Field(description="PCI device capability information.")
    controller_type: str | None = Field(
        description="Type of controller this device provides. `null` if not a controller.",
    )
    iommu_group: VMDeviceIOMMUGroup | None = Field(
        default=None,
        description="IOMMU group information for device isolation. `null` if IOMMU not available.",
    )
    available: bool = Field(description="Whether the device is available for passthrough to virtual machines.")
    drivers: list[str] = Field(description="Array of kernel drivers currently bound to this device.")
    error: str | None = Field(
        description="Error message if the device cannot be used for passthrough. `null` if no error.",
    )
    reset_mechanism_defined: bool = Field(
        description="Whether the device supports proper reset mechanisms for passthrough.",
    )
    description: str = Field(description="Human-readable description of the PCI device.")
    critical: bool = Field(description="Whether this device is critical to host system operation.")
    device_path: str | None = Field(description="Device filesystem path. `null` if not available.")


class VMDevicePassthroughDeviceResult(BaseModel):
    result: VMDevicePassthroughDevice = Field(
        description="Detailed information about the specified PCI passthrough device.",
    )


class VMDevicePassthroughInfo(RootModel[dict[str, VMDevicePassthroughDevice]]):
    pass


class VMDevicePassthroughDeviceChoicesArgs(BaseModel):
    pass


class VMDevicePassthroughDeviceChoicesResult(BaseModel):
    result: VMDevicePassthroughInfo = Field(
        description="Object of available PCI devices for passthrough with their detailed information.",
    )


class VMDevicePptdevChoicesArgs(BaseModel):
    pass


class VMDevicePptdevChoicesResult(BaseModel):
    result: VMDevicePassthroughInfo = Field(
        description="Object of PCI passthrough devices with their availability status.",
    )


class USBCapability(BaseModel):
    product: str | None = Field(description="USB product name. `null` if not available.")
    product_id: str | None = Field(description="USB product identifier. `null` if not available.")
    vendor: str | None = Field(description="USB vendor name. `null` if not available.")
    vendor_id: str | None = Field(description="USB vendor identifier. `null` if not available.")
    bus: str | None = Field(description="USB bus number. `null` if not available.")
    device: str | None = Field(description="USB device number on bus. `null` if not available.")


class VMDeviceUsbPassthroughDeviceArgs(BaseModel):
    device: NonEmptyString = Field(description="USB device identifier to get passthrough information for.")


class USBPassthroughDevice(BaseModel):
    capability: USBCapability = Field(description="USB device capability and identification information.")
    available: bool = Field(description="Whether the USB device is available for passthrough to virtual machines.")
    error: str | None = Field(
        description="Error message if the device cannot be used for passthrough. `null` if no error.",
    )


class USBPassthroughInfo(RootModel[dict[str, USBPassthroughDevice]]):
    pass


class VMDeviceUsbPassthroughDeviceResult(BaseModel):
    result: USBPassthroughDevice = Field(description="Detailed information about the specified USB passthrough device.")


class VMDeviceUsbPassthroughChoicesArgs(BaseModel):
    pass


class VMDeviceUsbPassthroughChoicesResult(BaseModel):
    result: USBPassthroughInfo = Field(
        description="Object of available USB devices for passthrough with their detailed information.",
    )


class VMDeviceUsbControllerChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceUsbControllerChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    """Available USB controller types for virtual machines."""


@single_argument_args('vm_convert')
class VMDeviceConvertArgs(BaseModel):
    source: NonEmptyString = Field(description="Source path for the conversion (disk image file or ZFS volume).")
    destination: NonEmptyString = Field(
        description="Destination path for the conversion (disk image file or ZFS volume).",
    )


class VMDeviceConvertResult(BaseModel):
    result: bool = Field(description="Whether the conversion operation was successful.")


@single_argument_args('vm_virtual_size')
class VMDeviceVirtualSizeArgs(BaseModel):
    path: str = Field(description="Absolute path to the disk image.")


class VMDeviceVirtualSizeResult(BaseModel):
    result: int = Field(description="The virtual size of the disk image in bytes.")
