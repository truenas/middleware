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
"""

from __future__ import annotations

import typing

from truenas_pylibvirt.utils.usb import get_all_usb_devices, parse_libvirt_device_name

from middlewared.plugins.container.migrate import find_usb_device_name_by_bus_and_devnum


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    plugged_in = set(await middleware.run_in_thread(get_all_usb_devices))

    # `False` for containers: every name in that table is a bus and device number pair, so there is
    # no already-correct case to preserve.
    for datastore, may_already_be_a_port in (("container.device", False), ("vm.device", True)):
        for device in await middleware.call("datastore.query", datastore):
            attributes = device["attributes"]
            if attributes.get("dtype") != "USB" or not (stored := attributes.get("device")):
                continue

            if may_already_be_a_port and stored in plugged_in:
                continue

            if not (address := parse_libvirt_device_name(stored)):
                middleware.logger.warning(
                    "%s %r: USB device %r names neither a port nor a bus and device number; "
                    "the device has to be selected again.",
                    datastore,
                    device["id"],
                    stored,
                )
                continue

            name = await middleware.run_in_thread(find_usb_device_name_by_bus_and_devnum, *address)
            if name is None:
                middleware.logger.warning(
                    "%s %r: nothing is plugged into bus %s device %s, so USB device %r cannot be "
                    "resolved to a port; the device has to be selected again.",
                    datastore,
                    device["id"],
                    *address,
                    stored,
                )
                continue

            if name == stored:
                continue

            middleware.logger.info(
                "%s %r: USB device %r is plugged into port %r; updating it.",
                datastore,
                device["id"],
                stored,
                name,
            )
            await middleware.call(
                "datastore.update",
                datastore,
                device["id"],
                {"attributes": attributes | {"device": name}},
            )
