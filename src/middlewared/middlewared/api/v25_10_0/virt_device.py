from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field, field_validator

from middlewared.api.base import BaseModel, LocalGID, LocalUID, match_validator, NonEmptyString, single_argument_args
from middlewared.validators import RE_MAC_ADDRESS


__all__ = [
    'DeviceType', 'InstanceType', 'VirtDeviceUSBChoicesArgs', 'VirtDeviceUSBChoicesResult',
    'VirtDeviceGPUChoicesArgs', 'VirtDeviceGPUChoicesResult', 'VirtDeviceDiskChoicesArgs',
    'VirtDeviceDiskChoicesResult', 'VirtDeviceNICChoicesArgs', 'VirtDeviceNICChoicesResult',
    'VirtDeviceExportDiskImageArgs', 'VirtDeviceExportDiskImageResult', 'VirtDeviceImportDiskImageArgs',
    'VirtDeviceImportDiskImageResult', 'VirtDevicePCIChoicesArgs', 'VirtDevicePCIChoicesResult',
    'VirtInstanceBootableDiskArgs', 'VirtInstanceBootableDiskResult',
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
    description: NonEmptyString | None = None
    readonly: bool = False


class Disk(Device):
    dev_type: Literal['DISK']
    source: NonEmptyString | None = None
    '''
    For CONTAINER instances, this would be a valid pool path. For VM instances, it
    can be a valid zvol path or an incus storage volume name
    '''
    destination: str | None = None
    boot_priority: int | None = Field(default=None, ge=0)
    io_bus: Literal['NVME', 'VIRTIO-BLK', 'VIRTIO-SCSI', None] = None
    storage_pool: NonEmptyString | None = None
    '''
    Storage pool in which the device is located. This must be one
    of the storage pools listed in virt.global.config output.
    If this is set to None during device creation, then the default storage
    pool defined in virt.global.config will be used.
    '''

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
    network: NonEmptyString | None = None
    nic_type: NicType | None = None
    parent: NonEmptyString | None = None
    mac: MAC = None


class USB(Device):
    dev_type: Literal['USB']
    bus: int | None = None
    dev: int | None = None
    product_id: str | None = None
    vendor_id: str | None = None


Proto: TypeAlias = Literal['UDP', 'TCP']


class Proxy(Device):
    dev_type: Literal['PROXY']
    source_proto: Proto
    source_port: int = Field(ge=1, le=65535)
    dest_proto: Proto
    dest_port: int = Field(ge=1, le=65535)


class TPM(Device):
    dev_type: Literal['TPM']
    path: str | None = None
    pathrm: str | None = None


GPUType: TypeAlias = Literal['PHYSICAL', 'MDEV', 'MIG', 'SRIOV']


class GPU(Device):
    dev_type: Literal['GPU']
    gpu_type: GPUType
    id: str | None = None
    gid: LocalGID | None = None
    uid: LocalUID | None = None
    mode: str | None = None
    mdev: NonEmptyString | None = None
    mig_uuid: NonEmptyString | None = None
    pci: NonEmptyString | None = None
    productid: NonEmptyString | None = None
    vendorid: NonEmptyString | None = None


class PCI(Device):
    dev_type: Literal['PCI']
    address: NonEmptyString


DeviceType: TypeAlias = Annotated[
    Disk | GPU | Proxy | TPM | USB | NIC | PCI,
    Field(discriminator='dev_type')
]


class VirtDeviceUSBChoicesArgs(BaseModel):
    pass


class USBChoice(BaseModel):
    vendor_id: str
    product_id: str
    bus: int
    dev: int
    product: str | None
    manufacturer: str | None


class VirtDeviceUSBChoicesResult(BaseModel):
    result: dict[str, USBChoice]


class VirtDeviceGPUChoicesArgs(BaseModel):
    gpu_type: GPUType


class GPUChoice(BaseModel):
    bus: str
    slot: str
    description: str
    vendor: str | None = None
    pci: str


class VirtDeviceGPUChoicesResult(BaseModel):
    result: dict[str, GPUChoice]


class VirtDeviceDiskChoicesArgs(BaseModel):
    pass


class VirtDeviceDiskChoicesResult(BaseModel):
    result: dict[str, str]


class VirtDeviceNICChoicesArgs(BaseModel):
    nic_type: NicType


class VirtDeviceNICChoicesResult(BaseModel):
    result: dict[str, str]


@single_argument_args('virt_device_import_disk_image')
class VirtDeviceImportDiskImageArgs(BaseModel):
    diskimg: NonEmptyString
    zvol: NonEmptyString


class VirtDeviceImportDiskImageResult(BaseModel):
    result: bool


@single_argument_args('virt_device_export_disk_image')
class VirtDeviceExportDiskImageArgs(BaseModel):
    format: NonEmptyString
    directory: NonEmptyString
    zvol: NonEmptyString


class VirtDeviceExportDiskImageResult(BaseModel):
    result: bool


class VirtDevicePCIChoicesArgs(BaseModel):
    pass


class VirtDevicePCIChoicesResult(BaseModel):
    result: dict


class VirtInstanceBootableDiskArgs(BaseModel):
    id: NonEmptyString
    disk: NonEmptyString


class VirtInstanceBootableDiskResult(BaseModel):
    result: bool
