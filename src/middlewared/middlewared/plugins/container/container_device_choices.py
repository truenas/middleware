from __future__ import annotations

from truenas_pylibvirt.utils.usb import get_all_usb_devices

from middlewared.api.current import ContainerDeviceNicAttachChoices, USBPassthroughDevice
from middlewared.service import ServiceContext

from .bridge import container_bridge_name


def nic_attach_choices(context: ServiceContext) -> ContainerDeviceNicAttachChoices:
    container_bridge = container_bridge_name(context)
    bridge: list[str] = [container_bridge]
    macvlan: list[str] = []
    for inf in context.middleware.call_sync("interface.choices", {"exclude": ["epair", "tap", "vnet"]}):
        if inf.startswith("br"):
            bridge.append(inf)
        else:
            macvlan.append(inf)
    return ContainerDeviceNicAttachChoices(BRIDGE=bridge, MACVLAN=macvlan)


def usb_choices() -> dict[str, USBPassthroughDevice]:
    return {
        key: USBPassthroughDevice(**value)
        for key, value in get_all_usb_devices().items()
    }


async def gpu_choices(context: ServiceContext) -> dict[str, str]:
    return {
        gpu["addr"]["pci_slot"]: gpu["vendor"]
        for gpu in await context.middleware.call("device.get_gpus")
        if gpu["vendor"] in ("AMD", "INTEL", "NVIDIA") and gpu["available_to_host"]
    }
