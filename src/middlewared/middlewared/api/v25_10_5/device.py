from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ["DeviceGetInfoArgs", "DeviceGetInfoResult"]


class SerialInfo(BaseModel):
    name: str = Field(description="Device name for the serial port.")
    location: str = Field(description="Physical location or path of the serial device.")
    drivername: str = Field(description="Name of the kernel driver handling this serial device.")
    start: str = Field(description="Starting address or identifier for the serial device.")
    size: int = Field(description="Size or capacity information for the serial device.")
    description: str = Field(description="Human-readable description of the serial device.")


class GPUInfoAddr(BaseModel):
    pci_slot: str = Field(description="PCI slot identifier for the GPU.")
    domain: str = Field(description="PCI domain number.")
    bus: str = Field(description="PCI bus number.")
    slot: str = Field(description="PCI slot number.")


class GPUInfoDevice(BaseModel):
    pci_id: str = Field(description="PCI device identifier.")
    pci_slot: str = Field(description="PCI slot location.")
    vm_pci_slot: str = Field(description="Virtual machine PCI slot mapping.")


class GPUInfo(BaseModel):
    addr: GPUInfoAddr = Field(description="PCI address information for the GPU.")
    description: str = Field(description="Human-readable description of the GPU.")
    devices: list[GPUInfoDevice] = Field(description="Array of PCI devices associated with this GPU.")
    vendor: str | None = Field(description="GPU vendor name or `null` if unknown.")
    available_to_host: bool = Field(description="Whether the GPU is available for use by the host system.")
    uses_system_critical_devices: bool = Field(
        description="Whether the GPU uses devices critical for system operation.",
    )
    critical_reason: str | None = Field(description="Reason why GPU is considered critical or `null` if not critical.")

    class Config:
        extra = "allow"


class DeviceGetInfoDisk(BaseModel):
    type: Literal["DISK"] = Field(description="Get disk info.")
    get_partitions: bool = Field(
        default=False,
        description=(
            "If set, query partition information for the disks. **NOTE: This can be expensive on systems with a large "
            "number of disks present.**"
        ),
    )
    serials_only: bool = Field(
        default=False,
        description="If set, query _ONLY_ serial information for the disks (overrides `get_partitions`).",
    )


class DeviceGetInfoOther(BaseModel):
    type: Literal["SERIAL", "GPU"] = Field(description="Get info for either serial devices or GPUs.")


class DeviceGetInfoArgs(BaseModel):
    data: DeviceGetInfoDisk | DeviceGetInfoOther = Field(
        description="Device information query parameters specifying type and options.",
    )


class DeviceGetInfoResult(BaseModel):
    result: dict[str, str] | dict[str, dict] | list[SerialInfo] | list[GPUInfo] = Field(
        description="Return an object if `type=\"DISK\"` or an array otherwise.",
    )
