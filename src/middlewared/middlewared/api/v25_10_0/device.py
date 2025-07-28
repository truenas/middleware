from typing import Literal

from middlewared.api.base import BaseModel


__all__ = ["DeviceGetInfoArgs", "DeviceGetInfoResult"]


class SerialInfo(BaseModel):
    name: str
    """Device name for the serial port."""
    location: str
    """Physical location or path of the serial device."""
    drivername: str
    """Name of the kernel driver handling this serial device."""
    start: str
    """Starting address or identifier for the serial device."""
    size: int
    """Size or capacity information for the serial device."""
    description: str
    """Human-readable description of the serial device."""


class GPUInfoAddr(BaseModel):
    pci_slot: str
    """PCI slot identifier for the GPU."""
    domain: str
    """PCI domain number."""
    bus: str
    """PCI bus number."""
    slot: str
    """PCI slot number."""


class GPUInfoDevice(BaseModel):
    pci_id: str
    """PCI device identifier."""
    pci_slot: str
    """PCI slot location."""
    vm_pci_slot: str
    """Virtual machine PCI slot mapping."""


class GPUInfo(BaseModel):
    addr: GPUInfoAddr
    """PCI address information for the GPU."""
    description: str
    """Human-readable description of the GPU."""
    devices: list[GPUInfoDevice]
    """Array of PCI devices associated with this GPU."""
    vendor: str | None
    """GPU vendor name or `null` if unknown."""
    available_to_host: bool
    """Whether the GPU is available for use by the host system."""
    uses_system_critical_devices: bool
    """Whether the GPU uses devices critical for system operation."""
    critical_reason: str | None
    """Reason why GPU is considered critical or `null` if not critical."""

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
    """Device information query parameters specifying type and options."""


class DeviceGetInfoResult(BaseModel):
    result: dict[str, str] | dict[str, dict] | list[SerialInfo] | list[GPUInfo]
    """Return an object if `type="DISK"` or an array otherwise."""
