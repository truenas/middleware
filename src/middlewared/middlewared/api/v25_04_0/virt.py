from typing import Literal, List, Union, Optional, TypeAlias
from typing_extensions import Annotated

from pydantic import Field, StringConstraints

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, NonEmptyString,
    LocalGID, LocalUID,
    single_argument_args, single_argument_result,
)


class VirtGlobalEntry(BaseModel):
    id: int
    pool: str | None = None
    dataset: str | None = None
    bridge: str | None = None
    v4_network: str | None = None
    v6_network: str | None = None
    state: Literal['INITIALIZING', 'INITIALIZED', 'NO_POOL', 'ERROR', 'LOCKED'] | None = None


@single_argument_args('virt_global_update')
class VirtGlobalUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    pool: NonEmptyString | None = None
    bridge: NonEmptyString | None = None
    v4_network: str | None = None
    v6_network: str | None = None


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


REMOTE_CHOICES: TypeAlias = Literal['LINUX_CONTAINERS']


@single_argument_args('virt_instances_image_choices')
class VirtInstanceImageChoicesArgs(BaseModel):
    remote: REMOTE_CHOICES = 'LINUX_CONTAINERS'


class ImageChoiceItem(BaseModel):
    label: str
    os: str
    release: str
    arch: str
    variant: str


class VirtInstanceImageChoicesResult(BaseModel):
    result: dict[str, ImageChoiceItem]


class Device(BaseModel):
    name: Optional[NonEmptyString] = None
    readonly: bool = False


class Disk(Device):
    dev_type: Literal['DISK']
    source: Optional[str] = None
    destination: Optional[str] = None


class NIC(Device):
    dev_type: Literal['NIC']
    network: NonEmptyString


class USB(Device):
    dev_type: Literal['USB']
    bus: Optional[int] = None
    dev: Optional[int] = None
    product_id: Optional[str] = None
    vendor_id: Optional[str] = None


Proto: TypeAlias = Literal['UDP', 'TCP']


class Proxy(Device):
    dev_type: Literal['PROXY']
    source_proto: Proto
    source_port: int
    dest_proto: Proto
    dest_port: int


class TPM(Device):
    dev_type: Literal['TPM']
    path: Optional[str] = None
    pathrm: Optional[str] = None


GPUType: TypeAlias = Literal['PHYSICAL', 'MDEV', 'MIG', 'SRIOV']


class GPU(Device):
    dev_type: Literal['GPU']
    gpu_type: GPUType
    id: str | None = None
    gid: LocalGID | None = None
    uid: LocalUID | None = None
    mode: Optional[str] = None
    mdev: Optional[NonEmptyString] = None
    mig_uuid: Optional[NonEmptyString] = None
    pci: Optional[NonEmptyString] = None
    productid: Optional[NonEmptyString] = None
    vendorid: Optional[NonEmptyString] = None


DeviceType: TypeAlias = Annotated[
    Union[Disk, GPU, Proxy, TPM, USB, NIC],
    Field(discriminator='dev_type')
]


class VirtInstanceAlias(BaseModel):
    type: Literal['INET', 'INET6']
    address: NonEmptyString
    netmask: int


InstanceType: TypeAlias = Literal['CONTAINER', 'VM']


class Image(BaseModel):
    architecture: str | None
    description: str | None
    os: str | None
    release: str | None
    serial: str | None
    type: str | None
    variant: str | None


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
    image: Image
    raw: dict


@single_argument_args('virt_instance_create')
class VirtInstanceCreateArgs(BaseModel):
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    image: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    remote: REMOTE_CHOICES = 'LINUX_CONTAINERS'
    instance_type: InstanceType = 'CONTAINER'
    environment: dict[str, str] | None = None
    autostart: bool | None = True
    cpu: str | None = None
    memory: int | None = None
    devices: List[DeviceType] = None


class VirtInstanceCreateResult(BaseModel):
    result: VirtInstanceEntry


class VirtInstanceUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    environment: dict[str, str] | None = None
    autostart: bool | None = None
    cpu: str | None = None
    memory: int | None = None


class VirtInstanceUpdateArgs(BaseModel):
    id: str
    virt_instance_update: VirtInstanceUpdate


class VirtInstanceUpdateResult(BaseModel):
    result: VirtInstanceEntry


class VirtInstanceDeleteArgs(BaseModel):
    id: str


class VirtInstanceDeleteResult(BaseModel):
    result: Literal[True]


class VirtInstanceDeviceListArgs(BaseModel):
    id: str


class VirtInstanceDeviceListResult(BaseModel):
    result: List[DeviceType]


class VirtInstanceDeviceAddArgs(BaseModel):
    id: str
    device: DeviceType


class VirtInstanceDeviceAddResult(BaseModel):
    result: dict


class VirtInstanceDeviceDeleteArgs(BaseModel):
    id: str
    name: str


class VirtInstanceDeviceDeleteResult(BaseModel):
    result: dict


class VirtInstanceStartArgs(BaseModel):
    id: str


class VirtInstanceStartResult(BaseModel):
    result: bool


class StopArgs(BaseModel):
    timeout: int = -1
    force: bool = False


class VirtInstanceStopArgs(BaseModel):
    id: str
    stop_args: StopArgs


class VirtInstanceStopResult(BaseModel):
    result: bool


class VirtInstanceRestartArgs(BaseModel):
    id: str
    stop_args: StopArgs


class VirtInstanceRestartResult(BaseModel):
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


class VirtDeviceDiskChoicesArgs(BaseModel):
    pass


class VirtDeviceDiskChoicesResult(BaseModel):
    result: dict[str, str]


class VirtImageUploadArgs(BaseModel):
    pass


@single_argument_result
class VirtImageUploadResult(BaseModel):
    fingerprint: NonEmptyString
    size: int
