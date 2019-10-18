# -*- coding=utf-8 -*-
import logging
import re
from packaging import version

from middlewared.utils import run

logger = logging.getLogger(__name__)

__all__ = ["annotate_devices_with_areca_dev_id"]

FIRMWARE_VERSION = re.compile(r"Firmware Version\s*: V([0-9.]+)")
V_1_51 = version.parse("1.51")

DISK = re.compile(r"\s*(?P<dev_id>[0-9]+)\s+(?P<enclosure>[0-9]+)\s+(Slot#|SLOT )(?P<slot>[0-9]+)")


async def annotate_devices_with_areca_dev_id(devices):
    areca_devices = [device for device in devices.values() if device["driver"].startswith("arcmsr")]

    for device in areca_devices:
        device["areca_dev_id"] = device["lun_id"] + 1 + device["channel_no"] * 8

    try:
        sys_info = await run("areca-cli", "sys", "info", encoding="utf-8")
        firmware_version = FIRMWARE_VERSION.search(sys_info.stdout)
        if firmware_version is None:
            logger.trace("Failed to parse areca controller firmware version")
            return
        if version.parse(firmware_version.group(1)) < V_1_51:
            logger.trace("Areca controller version does not support enclosures")
            return

        disk_info = await run("areca-cli", "disk", "info", encoding="utf-8")
        for line in disk_info.stdout.split("\n"):
            m = DISK.match(line)
            if m is None:
                continue

            dev_id = int(m.group("dev_id"))
            enclosure = int(m.group("enclosure"))
            slot = int(m.group("slot"))

            for device in areca_devices:
                if device["areca_dev_id"] == dev_id:
                    device["areca_dev_id"] = f"{slot}/{enclosure}"
                    break
    except Exception:
        logger.trace("Error in annotate_devices_with_areca_enclosure", exc_info=True)
