from typing import Literal, List, Union, Optional, TypeAlias
from typing_extensions import Annotated

from pydantic import Field, StringConstraints

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, NonEmptyString,
    single_argument_args, single_argument_result,
)


class VirtGlobalEntry(BaseModel):
    id: int
    pool: str | None = None
    dataset: str | None = None
    bridge: str | None = None
    state: str | None = None


@single_argument_args('virt_global_update')
class VirtGlobalUpdateArgs(BaseModel):
    pool: str | None = None
    bridge: str | None = None


class VirtGlobalUpdateResult(BaseModel):
    result: VirtGlobalEntry


class VirtGlobalBridgeChoicesArgs(BaseModel):
    pass


class VirtGlobalBridgeChoicesResult(BaseModel):
    result: dict


class VirtGlobalPoolChoicesArgs(BaseModel):
    pass


class VirtGlobalPoolChoicesResult(BaseModel):
    result: dict


class VirtGlobalGetNetworkArgs(BaseModel):
    name: NonEmptyString


@single_argument_result
class VirtGlobalGetNetworkResult(BaseModel):
    type: Literal['BRIDGE']
    managed: bool
    ipv4_address: NonEmptyString
    ipv4_nat: bool
    ipv6_address: NonEmptyString
    ipv6_nat: bool


REMOTE_CHOICES: TypeAlias = Optional[Literal['LINUX_CONTAINERS']]


@single_argument_args('virt_instances_image_choices')
class VirtInstancesImageChoicesArgs(BaseModel):
    remote: REMOTE_CHOICES = None


class ImageChoiceItem(BaseModel):
    label: str
    os: str
    release: str
    arch: str
    variant: int


class VirtInstancesImageChoicesResult(BaseModel):
    result: dict[str, ImageChoiceItem]


class Device(BaseModel):
    name: Optional[NonEmptyString] = None
    dev_type: Literal['USB', 'TPM', 'DISK', 'GPU', 'NIC', 'PROXY']
    readonly: bool = False


class Disk(Device):
    source: Optional[str] = None
    destination: Optional[str] = None


class NIC(Device):
    network: NonEmptyString


class USB(Device):
    bus: Optional[int] = None
    dev: Optional[int] = None
    product_id: Optional[str] = None
    vendor_id: Optional[str] = None


Proto: TypeAlias = Literal['UDP', 'TCP']


class Proxy(Device):
    source_proto: Proto
    source_port: int
    dest_proto: Proto
    dest_port: int


class TPM(Device):
    path: Optional[str] = None
    pathrm: Optional[str] = None


GPUType: TypeAlias = Literal['PHYSICAL', 'MDEV', 'MIG', 'SRIOV']


class GPU(Device):
    gpu_type: GPUType
    id: str | None = None
    gid: Optional[int] = None
    uid: Optional[int] = None
    mode: Optional[int] = None
    mdev: Optional[NonEmptyString] = None
    mig_uuid: Optional[NonEmptyString] = None
    pci: Optional[NonEmptyString] = None
    productid: Optional[NonEmptyString] = None
    vendorid: Optional[NonEmptyString] = None


Devices: TypeAlias = List[Union[Disk, GPU, Proxy, TPM, USB]]


class VirtInstanceAlias(BaseModel):
    type: Literal['INET', 'INET6']
    address: NonEmptyString
    netmask: int


InstanceType: TypeAlias = Literal['CONTAINER', 'VM']


class VirtInstanceEntry(BaseModel):
    id: str
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    type: InstanceType = 'CONTAINER'
    status: Literal['RUNNING', 'STOPPED']
    cpu: str | None
    memory: int
    autostart: bool
    environment: dict[str, str]
    aliases: List[VirtInstanceAlias]
    raw: dict


@single_argument_args('virt_instance_create')
class VirtInstancesCreateArgs(BaseModel):
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    image: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    remote: REMOTE_CHOICES = None
    instance_type: InstanceType = 'CONTAINER'
    environment: dict | None = None
    autostart: bool | None = None
    cpu: str | None = None
    memory: int | None = None
    devices: Devices = None


class VirtInstancesCreateResult(BaseModel):
    result: dict


class VirtInstancesUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    environment: dict | None = None
    autostart: bool | None = None
    cpu: str | None = None
    memory: int | None = None


class VirtInstancesUpdateArgs(BaseModel):
    id: str
    virt_instance_update: VirtInstancesUpdate


class VirtInstancesUpdateResult(BaseModel):
    result: VirtInstanceEntry


class VirtInstancesDeleteArgs(BaseModel):
    id: str


class VirtInstancesDeleteResult(BaseModel):
    result: Literal[True]


class VirtInstancesDeviceListArgs(BaseModel):
    id: str


class VirtInstancesDeviceListResult(BaseModel):
    result: List[Devices]


class VirtInstancesDeviceAddArgs(BaseModel):
    id: str
    device: Union[Disk, GPU, NIC, Proxy, TPM, USB] = Field(..., descriminator='dev_type')


class VirtInstancesDeviceAddResult(BaseModel):
    result: dict


class VirtInstancesDeviceDeleteArgs(BaseModel):
    id: str
    name: str


class VirtInstancesDeviceDeleteResult(BaseModel):
    result: dict


class VirtInstancesStateArgs(BaseModel):
    id: str
    action: Literal['START', 'STOP', 'RESTART']
    force: bool = False


class VirtInstancesStateResult(BaseModel):
    result: bool


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
    bus: int
    slot: int
    description: str
    vendor: Optional[str] = None


class VirtDeviceGPUChoicesResult(BaseModel):
    result: dict[str, GPUChoice]
