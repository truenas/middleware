from pydantic import ConfigDict, Discriminator, Field, model_validator
from typing import Annotated, Literal, TypeAlias

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)
from middlewared.utils.usb import USB_PORT_PATTERN

from .vm_device import USBAttributes, USBPassthroughDevice


__all__ = [
    'ContainerNICDevice', 'ContainerUSBDevice', 'ContainerDeviceType',
    'ContainerFilesystemDevice', 'ContainerGPUDevice',
    'ContainerDeviceEntry', 'ContainerDeviceCreateArgs', 'ContainerDeviceCreateResult', 'ContainerDeviceUpdateArgs',
    'ContainerDeviceUpdateResult', 'ContainerDeviceDeleteArgs', 'ContainerDeviceDeleteResult',
    'ContainerDeviceDiskChoicesArgs', 'ContainerDeviceDiskChoicesResult', 'ContainerDeviceNicAttachChoicesArgs',
    'ContainerDeviceNicAttachChoicesResult', 'ContainerDeviceUsbChoicesArgs', 'ContainerDeviceUsbChoicesResult',
    'ContainerDeviceGpuChoicesArgs', 'ContainerDeviceGpuChoicesResult',
]


class ContainerFilesystemDevice(BaseModel):
    dtype: Literal['FILESYSTEM'] = Field(description="Device type identifier for FILESYSTEM devices.")
    target: NonEmptyString = Field(
        pattern=r'^[^{}]*$',
        description="Path inside the container to mount the source at. Must not contain braces.",
    )
    source: NonEmptyString = Field(
        pattern=r'^[^{}]*$',
        description="Host path to bind-mount into the container. Must reside within a pool (under "
        "`/mnt`) and must not contain braces.",
    )


class ContainerGPUDevice(BaseModel):
    dtype: Literal['GPU'] = Field(description="Device type identifier for GPU devices.")
    gpu_type: Literal['AMD', 'INTEL', 'NVIDIA'] = Field(description="GPU device type.")
    pci_address: NonEmptyString = Field(description="PCI address of the GPU device on the host system.")


class ContainerNICDevice(BaseModel):
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


class ContainerUSBDevice(BaseModel):
    dtype: Literal['USB'] = Field(description="Device type identifier for USB devices.")
    usb: USBAttributes | None = Field(
        default=None,
        description="Vendor and product id of the host USB device to pass through. Whichever port that "
                    "device is plugged into is passed through. Mutually exclusive with `port`, so `null` "
                    "here means the device is identified by `port` instead.",
    )
    port: NonEmptyString | None = Field(
        default=None,
        pattern=USB_PORT_PATTERN,
        description="Host USB port to pass through, as a sysfs port path such as `1-4` or `1-4.2`. Whatever "
                    "device is plugged into this port at start time is passed through. Mutually exclusive "
                    "with `usb`, so `null` here means the device is identified by `usb` instead.",
    )

    @model_validator(mode='after')
    def validate_identity(self):
        if (self.port is None) == (self.usb is None):
            raise ValueError('Exactly one of `port` or `usb` must be specified')

        return self


ContainerDeviceType: TypeAlias = Annotated[
    ContainerFilesystemDevice | ContainerGPUDevice | ContainerNICDevice | ContainerUSBDevice,
    Discriminator('dtype')
]


class ContainerDeviceEntry(BaseModel):
    id: int = Field(description="Unique identifier for the containers device.")
    attributes: ContainerDeviceType = Field(description="Device-specific configuration attributes.")
    container: int = Field(description="ID of the container this device belongs to.")


class ContainerDeviceCreate(ContainerDeviceEntry):
    id: Excluded = excluded_field()


@single_argument_args('container_device_create')
class ContainerDeviceCreateArgs(ContainerDeviceCreate):
    pass


class ContainerDeviceCreateResult(BaseModel):
    result: ContainerDeviceEntry = Field(description="The newly created container device configuration.")


class ContainerDeviceUpdate(ContainerDeviceCreate, metaclass=ForUpdateMetaclass):
    # This will still get validated when update itself is called based off how we have
    # logic to validate different device types
    attributes: dict


class ContainerDeviceUpdateArgs(BaseModel):
    id: int = Field(description="ID of the container device to update.")
    container_device_update: ContainerDeviceUpdate = Field(
        description="Updated configuration for the container device.",
    )


class ContainerDeviceUpdateResult(BaseModel):
    result: ContainerDeviceEntry = Field(description="The updated container device configuration.")


class ContainerDeviceDeleteOptions(BaseModel):
    force: bool = Field(default=False, description="Force deletion even if the device is in use.")
    raw_file: bool = Field(default=False, description="Delete the underlying raw disk file when removing the device.")
    zvol: bool = Field(default=False, description="Delete the underlying ZFS volume when removing the device.")


class ContainerDeviceDeleteArgs(BaseModel):
    id: int = Field(description="ID of the container device to delete.")
    options: ContainerDeviceDeleteOptions = Field(
        default=ContainerDeviceDeleteOptions(),
        description="Options controlling the device deletion process.",
    )


class ContainerDeviceDeleteResult(BaseModel):
    result: bool = Field(description="Whether the container device was successfully deleted.")


class ContainerDeviceDiskChoicesArgs(BaseModel):
    pass


class ContainerDeviceDiskChoices(BaseModel):
    model_config = ConfigDict(extra='allow')


class ContainerDeviceDiskChoicesResult(BaseModel):
    result: ContainerDeviceDiskChoices = Field(
        description="Available disk devices and storage volumes for container attachment.",
    )


class ContainerDeviceNicAttachChoicesArgs(BaseModel):
    pass


@single_argument_result
class ContainerDeviceNicAttachChoicesResult(BaseModel):
    BRIDGE: list[str] = Field(description="Available bridge interfaces for NIC attachment.")
    MACVLAN: list[str] = Field(description="Available parent interfaces for creating MACVLAN NIC devices.")


class ContainerDeviceUsbChoicesArgs(BaseModel):
    pass


class ContainerDeviceUsbChoicesResult(BaseModel):
    result: dict[str, USBPassthroughDevice] = Field(
        description="Object of available USB devices for passthrough with their detailed information.",
    )


class ContainerDeviceGpuChoicesArgs(BaseModel):
    pass


class ContainerDeviceGpuChoicesResult(BaseModel):
    result: dict = Field(description="Available GPU(s) for container attachment.")
