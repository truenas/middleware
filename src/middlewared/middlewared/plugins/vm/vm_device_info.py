from __future__ import annotations

from middlewared.api.current import VMDeviceIotypeChoices, VMDeviceNicAttachChoices
from middlewared.service import ServiceContext


async def disk_choices(context: ServiceContext) -> dict[str, str]:
    out = {}
    zvols = await context.call2(
        context.s.zfs.resource.unlocked_zvols_fast, [
            ["OR", [["attachment", "=", None], ["attachment.method", "=", "vm.devices.query"]]],
            ["ro", "=", False],
        ],
        {}, ["ATTACHMENT", "RO"]
    )
    assert isinstance(zvols, list)
    for zvol in zvols:
        out[zvol["path"]] = zvol["name"]
    return out


def iotype_choices() -> VMDeviceIotypeChoices:
    return VMDeviceIotypeChoices()


async def nic_attach_choices(context: ServiceContext) -> VMDeviceNicAttachChoices:
    bridge: list[str] = []
    macvlan: list[str] = []
    for inf in await context.middleware.call("interface.choices", {"exclude": ["epair", "tap", "vnet"]}):
        if inf.startswith("br"):
            bridge.append(inf)
        else:
            macvlan.append(inf)
    return VMDeviceNicAttachChoices(BRIDGE=bridge, MACVLAN=macvlan)


async def bind_choices(context: ServiceContext) -> dict[str, str]:
    return {
        d["address"]: d["address"] for d in await context.middleware.call(
            "interface.ip_in_use", {"static": True, "any": True, "loopback": True}
        )
    }
