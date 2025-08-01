from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field, field_validator

from middlewared.api.base import BaseModel, LocalGID, LocalUID, match_validator, NonEmptyString, single_argument_args
from middlewared.validators import RE_MAC_ADDRESS


__all__ = [
    'DeviceType', 'InstanceType', 'VirtDeviceUsbChoicesArgs', 'VirtDeviceUsbChoicesResult',
    'VirtDeviceGpuChoicesArgs', 'VirtDeviceGpuChoicesResult', 'VirtDeviceDiskChoicesArgs',
    'VirtDeviceDiskChoicesResult', 'VirtDeviceNicChoicesArgs', 'VirtDeviceNicChoicesResult',
    'VirtDeviceExportDiskImageArgs', 'VirtDeviceExportDiskImageResult', 'VirtDeviceImportDiskImageArgs',
    'VirtDeviceImportDiskImageResult', 'VirtDevicePciChoicesArgs', 'VirtDevicePciChoicesResult',
    'VirtInstanceDeviceSetBootableDiskArgs', 'VirtInstanceDeviceSetBootableDiskResult',
]


InstanceType: TypeAlias = Literal['CONTAINER', 'VM']
MAC: TypeAlias = Annotated[
    str | None,
    AfterValidator(
        match_validator(
            RE_MAC_ADDRESS,
            'MAC address is not valid.'
        )
    )
]


class Device(BaseModel):
    name: NonEmptyString | None = None
    """Optional human-readable name for the virtualization device."""
    description: NonEmptyString | None = None
    """Optional description explaining the purpose or configuration of this device."""
    readonly: bool = False
    """Whether the device should be mounted in read-only mode."""


class Disk(Device):
    dev_type: Literal['DISK']
    """Device type identifier for virtual disk devices."""
    source: NonEmptyString | None = None
    """
    For CONTAINER instances, this would be a valid pool path. For VM instances, it \
    can be a valid zvol path or an incus storage volume name.
    """
    destination: str | None = None
    """Target path where the disk appears inside the virtualized instance."""
    boot_priority: int | None = Field(default=None, ge=0)
    """Boot priority for this disk device. Lower numbers boot first. `null` means non-bootable."""
    io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI', None] = None
    """Storage bus type for optimal performance and compatibility."""
    storage_pool: NonEmptyString | None = None
    """
    Storage pool in which the device is located. This must be one \
    of the storage pools listed in virt.global.config output.
    If this is set to None during device creation, then the default storage \
    pool defined in virt.global.config will be used.
    """

    @field_validator('source')
    @classmethod
    def validate_source(cls, source):
        if source is None or '/' not in source:
            return source

        # Source must be an absolute path now
        if not source.startswith(('/dev/zvol/', '/mnt/')):
            raise ValueError('Only pool paths are allowed')

        if source.startswith('/mnt/.ix-apps'):
            raise ValueError('Invalid source')

        return source


NicType: TypeAlias = Literal['BRIDGED', 'MACVLAN']


class NIC(Device):
    dev_type: Literal['NIC']
    """Device type identifier for network interface cards."""
    network: NonEmptyString | None = None
    """Name of the network to connect this NIC to."""
    nic_type: NicType | None = None
    """Type of network interface (bridged or macvlan)."""
    parent: NonEmptyString | None = None
    """Parent network interface on the host system."""
    mac: MAC = None
    """MAC address for the virtual network interface. `null` for auto-generated."""


class USB(Device):
    dev_type: Literal['USB']
    """Device type identifier for USB devices."""
    bus: int | None = None
    """USB bus number on the host system."""
    dev: int | None = None
    """USB device number on the specified bus."""
    product_id: str | None = None
    """USB product identifier for device matching."""
    vendor_id: str | None = None
    """USB vendor identifier for device matching."""


Proto: TypeAlias = Literal['UDP', 'TCP']


class Proxy(Device):
    dev_type: Literal['PROXY']
    """Device type identifier for network port forwarding."""
    source_proto: Proto
    """Network protocol (TCP or UDP) for the source connection."""
    source_port: int = Field(ge=1, le=65535)
    """Source port number on the host system to forward from."""
    dest_proto: Proto
    """Network protocol (TCP or UDP) for the destination connection."""
    dest_port: int = Field(ge=1, le=65535)
    """Destination port number inside the virtualized instance."""


class TPM(Device):
    dev_type: Literal['TPM']
    """Device type identifier for Trusted Platform Module devices."""
    path: str | None = None
    """Path to the TPM device on the host system."""
    pathrm: str | None = None
    """Resource manager path for TPM device access."""


GPUType: TypeAlias = Literal['PHYSICAL', 'MDEV', 'MIG', 'SRIOV']


class GPU(Device):
    dev_type: Literal['GPU']
    """Device type identifier for graphics processing units."""
    gpu_type: GPUType
    """Type of GPU virtualization (physical passthrough, mediated device, etc.)."""
    id: str | None = None
    """Unique identifier for the GPU device."""
    gid: LocalGID | None = None
    """Group ID for device permissions inside the container."""
    uid: LocalUID | None = None
    """User ID for device permissions inside the container."""
    mode: str | None = None
    """Permission mode for device access (e.g., '660')."""
    mdev: NonEmptyString | None = None
    """Mediated device identifier for GPU virtualization."""
    mig_uuid: NonEmptyString | None = None
    """Multi-Instance GPU UUID for NVIDIA GPU partitioning."""
    pci: NonEmptyString | None = None
    """PCI address of the GPU device on the host system."""
    productid: NonEmptyString | None = None
    """Product identifier for GPU device matching."""
    vendorid: NonEmptyString | None = None
    """Vendor identifier for GPU device matching."""


class PCI(Device):
    dev_type: Literal['PCI']
    """Device type identifier for PCI device passthrough."""
    address: NonEmptyString
    """PCI bus address of the device to pass through to the virtualized instance."""


class CDROM(Device):
    dev_type: Literal['CDROM']
    """Device type identifier for CD-ROM/DVD optical drives."""
    source: NonEmptyString
    """Path to the ISO image file or physical optical drive to mount."""
    boot_priority: int | None = Field(default=None, ge=0)
    """Boot priority for this optical device. Lower numbers boot first. `null` means non-bootable."""


DeviceType: TypeAlias = Annotated[
    Disk | GPU | Proxy | TPM | USB | NIC | PCI | CDROM,
    Field(discriminator='dev_type')
]


class VirtDeviceUsbChoicesArgs(BaseModel):
    pass


class USBChoice(BaseModel):
    vendor_id: str
    """USB vendor identifier for this device."""
    product_id: str
    """USB product identifier for this device."""
    bus: int
    """USB bus number where this device is connected."""
    dev: int
    """USB device number on the bus."""
    product: str | None
    """Product name of the USB device. `null` if not available."""
    manufacturer: str | None
    """Manufacturer name of the USB device. `null` if not available."""


class VirtDeviceUsbChoicesResult(BaseModel):
    result: dict[str, USBChoice]
    """Object of available USB devices with their hardware information."""


class VirtDeviceGpuChoicesArgs(BaseModel):
    gpu_type: GPUType
    """Type of GPU virtualization to filter available choices."""


class GPUChoice(BaseModel):
    bus: str
    """PCI bus identifier for the GPU device."""
    slot: str
    """PCI slot identifier for the GPU device."""
    description: str
    """Human-readable description of the GPU device."""
    vendor: str | None = None
    """GPU vendor name. `null` if not available."""
    pci: str
    """Complete PCI address of the GPU device."""


class VirtDeviceGpuChoicesResult(BaseModel):
    result: dict[str, GPUChoice]
    """Object of available GPU devices with their hardware information."""


class VirtDeviceDiskChoicesArgs(BaseModel):
    pass


class VirtDeviceDiskChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available disk devices and storage volumes for virtualization."""


class VirtDeviceNicChoicesArgs(BaseModel):
    nic_type: NicType
    """Type of network interface to filter available choices."""


class VirtDeviceNicChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available network interfaces for the specified NIC type."""


@single_argument_args('virt_device_import_disk_image')
class VirtDeviceImportDiskImageArgs(BaseModel):
    diskimg: NonEmptyString
    """Path to the disk image file to import."""
    zvol: NonEmptyString
    """Target ZFS volume path where the disk image will be imported."""


class VirtDeviceImportDiskImageResult(BaseModel):
    result: bool
    """Whether the disk image import operation was successful."""


@single_argument_args('virt_device_export_disk_image')
class VirtDeviceExportDiskImageArgs(BaseModel):
    format: NonEmptyString
    """Output format for the exported disk image (e.g., 'qcow2', 'raw')."""
    directory: NonEmptyString
    """Directory path where the exported disk image will be saved."""
    zvol: NonEmptyString
    """Source ZFS volume to export as a disk image."""


class VirtDeviceExportDiskImageResult(BaseModel):
    result: bool
    """Whether the disk image export operation was successful."""


class VirtDevicePciChoicesArgs(BaseModel):
    pass


class VirtDevicePciChoicesResult(BaseModel):
    result: dict
    """Object of available PCI devices that can be passed through to virtual instances."""


class VirtInstanceDeviceSetBootableDiskArgs(BaseModel):
    id: NonEmptyString
    """Identifier of the virtual instance to configure."""
    disk: NonEmptyString
    """Name or identifier of the disk device to set as bootable."""


class VirtInstanceDeviceSetBootableDiskResult(BaseModel):
    result: bool
    """Whether the bootable disk configuration was successfully applied."""
