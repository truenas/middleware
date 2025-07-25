from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field, model_validator, RootModel, Secret

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
]


class VMCDROMDevice(BaseModel):
    dtype: Literal['CDROM']
    """Device type identifier for CD-ROM/DVD devices."""
    path: NonEmptyString = Field(pattern='^/mnt/[^{}]*$')
    """Path must not contain "{", "}" characters, and it should start with "/mnt/"."""


class VMDisplayDevice(BaseModel):
    dtype: Literal['DISPLAY']
    """Device type identifier for display/graphics devices."""
    resolution: Literal[
        '1920x1200', '1920x1080', '1600x1200', '1600x900',
        '1400x1050', '1280x1024', '1280x720',
        '1024x768', '800x600', '640x480',
    ] = '1024x768'
    port: int | None = Field(default=None, ge=5900, le=65535)
    """VNC/SPICE port number for remote display access. `null` for auto-assignment."""
    web_port: int | None = Field(default=None, ge=5900, le=65535)
    """Web-based display access port number. `null` for auto-assignment."""
    bind: NonEmptyString = '127.0.0.1'
    """IP address to bind the display server to."""
    wait: bool = False
    """Whether to wait for a client connection before starting the VM."""
    password: Secret[NonEmptyString]
    """Password for display server authentication."""
    web: bool = True
    """Whether to enable web-based display access."""
    type_: Literal['SPICE'] = Field(alias='type', default='SPICE')
    """Display protocol type."""


class VMNICDevice(BaseModel):
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


class VMPCIDevice(BaseModel):
    dtype: Literal['PCI']
    """Device type identifier for PCI passthrough devices."""
    pptdev: NonEmptyString
    """Host PCI device identifier to pass through to the VM."""


class VMRAWDevice(BaseModel):
    dtype: Literal['RAW']
    """Device type identifier for raw disk devices."""
    path: NonEmptyString = Field(pattern='^[^{}]*$', description='Path must not contain "{", "}" characters.')
    type_: Literal['AHCI', 'VIRTIO'] = Field(alias='type', default='AHCI')
    exists: bool = False
    boot: bool = False
    size: int | None = None
    logical_sectorsize: Literal[None, 512, 4096] | None = None
    physical_sectorsize: Literal[None, 512, 4096] | None = None
    iotype: Literal['NATIVE', 'THREADS', 'IO_URING'] = 'THREADS'
    serial: NonEmptyString | None = None


class VMDiskDevice(BaseModel):
    dtype: Literal['DISK']
    path: NonEmptyString | None = None
    type_: Literal['AHCI', 'VIRTIO'] = Field(alias='type', default='AHCI')
    create_zvol: bool = False
    zvol_name: str | None = None
    zvol_volsize: int | None = None
    logical_sectorsize: Literal[None, 512, 4096] | None = None
    physical_sectorsize: Literal[None, 512, 4096] | None = None
    iotype: Literal['NATIVE', 'THREADS', 'IO_URING'] = 'THREADS'
    serial: NonEmptyString | None = None

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
    """Vendor id must start with "0x" prefix e.g 0x16a8."""
    product_id: NonEmptyString = Field(pattern='^0x.*')
    """Product id must start with "0x" prefix e.g 0x16a8."""


class VMUSBDevice(BaseModel):
    dtype: Literal['USB']
    usb: USBAttributes | None = None
    controller_type: Literal[
        'piix3-uhci', 'piix4-uhci', 'ehci', 'ich9-ehci1',
        'vt82c686b-uhci', 'pci-ohci', 'nec-xhci', 'qemu-xhci',
    ] = 'nec-xhci'
    device: NonEmptyString | None = None


VMDeviceType: TypeAlias = Annotated[
    VMCDROMDevice | VMDisplayDevice | VMNICDevice | VMPCIDevice | VMRAWDevice | VMDiskDevice | VMUSBDevice,
    Field(discriminator='dtype')
]


# VM Device Service models


class VMDeviceEntry(BaseModel):
    id: int
    attributes: VMDeviceType
    vm: int
    order: int


class VMDeviceCreate(VMDeviceEntry):
    order: int | None = None
    id: Excluded = excluded_field()


@single_argument_args('vm_device_create')
class VMDeviceCreateArgs(VMDeviceCreate):
    pass


class VMDeviceCreateResult(BaseModel):
    result: VMDeviceEntry


class VMDeviceUpdate(VMDeviceCreate, metaclass=ForUpdateMetaclass):
    pass


class VMDeviceUpdateArgs(BaseModel):
    id: int
    vm_device_update: VMDeviceUpdate


class VMDeviceUpdateResult(BaseModel):
    result: VMDeviceEntry


class VMDeviceDeleteOptions(BaseModel):
    force: bool = False
    raw_file: bool = False
    zvol: bool = False


class VMDeviceDeleteArgs(BaseModel):
    id: int
    options: VMDeviceDeleteOptions = VMDeviceDeleteOptions()


class VMDeviceDeleteResult(BaseModel):
    result: bool


class VMDeviceDiskChoicesArgs(BaseModel):
    pass


class VMDeviceDiskChoices(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMDeviceDiskChoicesResult(BaseModel):
    result: VMDeviceDiskChoices


class VMDeviceIotypeChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceIotypeChoicesResult(BaseModel):
    NATIVE: str = 'NATIVE'
    THREADS: str = 'THREADS'
    IO_URING: str = 'IO_URING'


class VMDeviceNicAttachChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceNicAttachChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMDeviceBindChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceBindChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMDeviceIommuEnabledArgs(BaseModel):
    pass


class VMDeviceIommuEnabledResult(BaseModel):
    result: bool


class VMDevicePassthroughDeviceArgs(BaseModel):
    device: NonEmptyString


class VMDeviceCapability(BaseModel):
    class_: str | None = Field(alias='class')
    domain: str | None
    bus: str | None
    slot: str | None
    function: str | None
    product: str | None
    vendor: str | None


class VMDeviceIOMMUGroupAddress(BaseModel):
    domain: str
    bus: str
    slot: str
    function: str


class VMDeviceIOMMUGroup(BaseModel):
    number: int
    addresses: list[VMDeviceIOMMUGroupAddress]


class VMDevicePassthroughDevice(BaseModel):
    capability: VMDeviceCapability
    controller_type: str | None
    iommu_group: VMDeviceIOMMUGroup | None = None
    available: bool
    drivers: list[str]
    error: str | None
    reset_mechanism_defined: bool
    description: str
    critical: bool
    device_path: str | None


class VMDevicePassthroughDeviceResult(BaseModel):
    result: VMDevicePassthroughDevice


class VMDevicePassthroughInfo(RootModel[dict[str, VMDevicePassthroughDevice]]):
    pass


class VMDevicePassthroughDeviceChoicesArgs(BaseModel):
    pass


class VMDevicePassthroughDeviceChoicesResult(BaseModel):
    result: VMDevicePassthroughInfo


class VMDevicePptdevChoicesArgs(BaseModel):
    pass


class VMDevicePptdevChoicesResult(BaseModel):
    result: VMDevicePassthroughInfo


class USBCapability(BaseModel):
    product: str | None
    product_id: str | None
    vendor: str | None
    vendor_id: str | None
    bus: str | None
    device: str | None


class VMDeviceUsbPassthroughDeviceArgs(BaseModel):
    device: NonEmptyString


class USBPassthroughDevice(BaseModel):
    capability: USBCapability
    available: bool
    error: str | None


class USBPassthroughInfo(RootModel[dict[str, USBPassthroughDevice]]):
    pass


class VMDeviceUsbPassthroughDeviceResult(BaseModel):
    result: USBPassthroughDevice


class VMDeviceUsbPassthroughChoicesArgs(BaseModel):
    pass


class VMDeviceUsbPassthroughChoicesResult(BaseModel):
    result: USBPassthroughInfo


class VMDeviceUsbControllerChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMDeviceUsbControllerChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
