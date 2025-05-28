from typing import Literal

from middlewared.api.base import BaseModel


__all__ = ["DeviceGetInfoArgs", "DeviceGetInfoResult"]


class SerialInfo(BaseModel):
    name: str
    location: str
    drivername: str
    start: str
    size: int
    description: str


class GPUInfoAddr(BaseModel):
    pci_slot: str
    domain: str
    bus: str
    slot: str


class GPUInfoDevice(BaseModel):
    pci_id: str
    pci_slot: str
    vm_pci_slot: str


class GPUInfo(BaseModel):
    addr: GPUInfoAddr
    description: str
    devices: list[GPUInfoDevice]
    vendor: str | None
    available_to_host: bool
    uses_system_critical_devices: bool
    critical_reason: str | None

    class Config:
        extra = "allow"


class DeviceGetInfoDisk(BaseModel):
    type: Literal["DISK"]
    """Get disk info."""
    get_partitions: bool = False
    """
    If set, query partition information for the disks.
    **NOTE: This can be expensive on systems with a large number of disks present.**
    """
    serials_only: bool = False
    """If set, query _ONLY_ serial information for the disks (overrides `get_partitions`)."""


class DeviceGetInfoOther(BaseModel):
    type: Literal["SERIAL", "GPU"]
    """Get info for either serial devices or GPUs."""


class DeviceGetInfoArgs(BaseModel):
    data: DeviceGetInfoDisk | DeviceGetInfoOther


class DeviceGetInfoResult(BaseModel):
    result: dict[str, str] | dict[str, dict] | list[SerialInfo] | list[GPUInfo]
    """Return an object if `type="DISK"` or an array otherwise."""
