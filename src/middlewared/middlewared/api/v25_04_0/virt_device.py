from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from middlewared.api.base import BaseModel, LocalGID, LocalUID, NonEmptyString


__all__ = [
    'DeviceType', 'InstanceType', 'VirtDeviceUSBChoicesArgs', 'VirtDeviceUSBChoicesResult',
    'VirtDeviceGPUChoicesArgs', 'VirtDeviceGPUChoicesResult', 'VirtDeviceDiskChoicesArgs',
    'VirtDeviceDiskChoicesResult', 'VirtDeviceNICChoicesArgs', 'VirtDeviceNICChoicesResult',
]


InstanceType: TypeAlias = Literal['CONTAINER', 'VM']


class Device(BaseModel):
    name: NonEmptyString | None = None
    description: NonEmptyString | None = None
    readonly: bool = False


class Disk(Device):
    dev_type: Literal['DISK']
    source: str | None = None
    destination: str | None = None


NicType: TypeAlias = Literal['BRIDGED', 'MACVLAN']


class NIC(Device):
    dev_type: Literal['NIC']
    network: NonEmptyString | None = None
    nic_type: NicType | None = None
    parent: NonEmptyString | None = None


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


DeviceType: TypeAlias = Annotated[
    Disk | GPU | Proxy | TPM | USB | NIC,
    Field(discriminator='dev_type')
]


class VirtDeviceUSBChoicesArgs(BaseModel):
    pass


class USBChoice(BaseModel):
    vendor_id: str
    product_id: str
    bus: int
    dev: int
    product: str
    manufacturer: str


class VirtDeviceUSBChoicesResult(BaseModel):
    result: dict[str, USBChoice]


class VirtDeviceGPUChoicesArgs(BaseModel):
    instance_type: InstanceType
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
