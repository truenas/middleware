"""Point stored USB passthrough devices at the port they are plugged into.

A USB device name is now built from the physical port (`usb_1_4` is port 1-4), which is what
libvirt has always called them and what 25.10 stored. The 26.0 pre-releases built the same shape
of name out of the bus and device numbers instead, and a device number is an enumeration counter
the kernel reissues on every replug, so those stored values name a port nobody chose.

Only the live hardware can map a device number back to a port, which is why this is a middleware
migration rather than an alembic one: it runs on the machine the devices are attached to, while
they are still attached.

`container_device` was created in 26.0 and has never existed in an earlier release, so every value
in it was written that way and is converted. A `vm_device` value may predate 26.0, so it is kept
whenever it already names a port that something is plugged into, and only converted otherwise.

A pair that resolves to nothing is left alone and logged: the device is unplugged, or the database
arrived from another machine through `config.upload`, and either way there is nothing here to
point it at. The stored name then fails at start with `USB device <name> not found` instead of
quietly passing through whichever device the digits happen to land on.

Two devices cannot share one port, so a converted name that lands on a port another device of the
same instance already holds is left alone too. Every value that is not rewritten claims its port
first, which is what keeps the outcome from depending on the order the rows are read in.
"""

from __future__ import annotations

import typing

from truenas_pylibvirt.utils.usb import get_all_usb_devices, parse_libvirt_device_name

from middlewared.plugins.container.migrate import (
    normalize_bus_and_devnum,
    usb_device_names_by_bus_and_devnum,
)


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


# Every table holding USB devices, with whether a stored name can already be a port, and the key
# the row's instance arrives under. `False` for containers: every name in that table is a bus and
# device number pair, so there is no already-correct case to preserve.
DATASTORES = (
    ("container.device", False, "container"),
    ("vm.device", True, "vm"),
)


def _instance(device: dict, parent: str) -> dict:
    # The instance is joined in by `datastore.query`. It is absent only for a row whose instance
    # has gone, which nothing else in the row lets us distinguish, so give those a shared identity.
    return device.get(parent) or {}


async def migrate(middleware: Middleware) -> None:
    plugged_in = set(await middleware.run_in_thread(get_all_usb_devices))
    port_names = await middleware.run_in_thread(usb_device_names_by_bus_and_devnum)

    for datastore, may_already_be_a_port, parent in DATASTORES:
        # Resolve every row before writing any of them, so a device that is already pointing at
        # its port can claim that port ahead of one that only resolves to it.
        keep, rewrite = [], []

        for device in await middleware.call("datastore.query", datastore):
            attributes = device["attributes"]
            if attributes.get("dtype") != "USB" or not (stored := attributes.get("device")):
                continue

            instance = _instance(device, parent)

            if may_already_be_a_port and stored in plugged_in:
                keep.append((device, stored, stored))
                continue

            if not (address := parse_libvirt_device_name(stored)):
                middleware.logger.warning(
                    "%s %r on %s %r: USB device %r names neither a port nor a bus and device "
                    "number; the device should be selected again.",
                    datastore,
                    device["id"],
                    parent,
                    instance.get("name"),
                    stored,
                )
                # A row that is left alone still holds whatever name it was storing, so it has to
                # claim it: a rename landing on that name would put two devices on one port.
                keep.append((device, stored, stored))
                continue

            name = port_names.get(normalize_bus_and_devnum(*address))
            if name is None:
                middleware.logger.warning(
                    "%s %r on %s %r: nothing is plugged into bus %s device %s, so USB device %r "
                    "cannot be resolved to a port; the device should be selected again.",
                    datastore,
                    device["id"],
                    parent,
                    instance.get("name"),
                    *address,
                    stored,
                )
                keep.append((device, stored, stored))
                continue

            (keep if name == stored else rewrite).append((device, stored, name))

        # One port, one device -- but only within an instance: two instances may each be
        # configured for the same device, and only one of them can be running at a time.
        claimed: dict[tuple[int | None, str], int] = {}
        for device, _, name in sorted(keep, key=lambda row: row[0]["id"]):
            claimed.setdefault((_instance(device, parent).get("id"), name), device["id"])

        for device, stored, name in sorted(rewrite, key=lambda row: row[0]["id"]):
            instance = _instance(device, parent)
            claim = (instance.get("id"), name)

            if (holder := claimed.get(claim)) is not None:
                middleware.logger.warning(
                    "%s %r on %s %r: USB device %r is plugged into port %r, which device %r "
                    "already uses; leaving it as-is.",
                    datastore,
                    device["id"],
                    parent,
                    instance.get("name"),
                    stored,
                    name,
                    holder,
                )
                continue

            claimed[claim] = device["id"]
            middleware.logger.info(
                "%s %r on %s %r: USB device %r is plugged into port %r; updating it.",
                datastore,
                device["id"],
                parent,
                instance.get("name"),
                stored,
                name,
            )
            try:
                await middleware.call(
                    "datastore.update",
                    datastore,
                    device["id"],
                    {"attributes": device["attributes"] | {"device": name}},
                )
            except Exception:
                # A migration that raises is not recorded, so it runs again from the start on the
                # next boot -- by which time the kernel has reissued the device numbers the rows
                # that did get written were resolved from. One row that cannot be written is worth
                # far less than that.
                middleware.logger.error(
                    "%s %r: failed to point USB device %r at port %r.",
                    datastore,
                    device["id"],
                    stored,
                    name,
                    exc_info=True,
                )
