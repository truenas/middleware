import pytest
from mock import Mock, patch

from middlewared.common.smart.smartctl import get_smartctl_args, SMARTCTX


@pytest.mark.asyncio
async def test__get_smartctl_args__disk_nonexistent():
    context = SMARTCTX(devices={}, enterprise_hardware=False)
    assert await get_smartctl_args(context, "sda", "") is None


@pytest.mark.asyncio
async def test__get_smartctl_args__nvme():
    context = SMARTCTX(devices={}, enterprise_hardware=False)
    assert await get_smartctl_args(context, "nvme0n1", "") == ["/dev/nvme0n1", "-d", "nvme"]


@pytest.mark.asyncio
async def test_get_disk__unknown_usb_bridge():
    context = SMARTCTX(
        devices={
            "sda": {
                "name": "sda",
                "sectorsize": 4096,
                "number": 2048,
                "subsystem": "scsi",
                "driver": "sd",
                "hctl": "17:0:0:0",
                "size": 10000831348736,
                "mediasize": 10000831348736,
                "ident": "ZZBBBAAA",
                "serial": "ZZBBBAAA",
                "model": "USB MODEL",
                "descr": "USB MODEL",
                "lunid": "5000cca251214158",
                "bus": "USB",
                "type": "SSD",
                "blocks": 19532873728,
                "serial_lunid": "ZZBBBAAA_5000cca251214158",
                "rotationrate": None,
                "stripesize": None,
                "parts": [],
                "dif": False
            },
        },
        enterprise_hardware=False,
    )
    assert await get_smartctl_args(context, "sda", "") == ["/dev/sda", "-d", "sat"]


@pytest.mark.asyncio
async def test_get_disk__generic():
    context = SMARTCTX(
        devices={
            "sda": {
                "name": "sda",
                "sectorsize": 4096,
                "number": 2048,
                "subsystem": "scsi",
                "driver": "sd",
                "hctl": "17:0:0:0",
                "size": 10000831348736,
                "mediasize": 10000831348736,
                "ident": "ZZBBBAAA",
                "serial": "ZZBBBAAA",
                "model": "USB MODEL",
                "descr": "USB MODEL",
                "lunid": "5000cca251214158",
                "bus": "scsi",
                "type": "HDD",
                "blocks": 19532873728,
                "serial_lunid": "ZZBBBAAA_5000cca251214158",
                "rotationrate": "7200",
                "stripesize": None,
                "parts": [],
                "dif": False
            },
        },
        enterprise_hardware=False,
    )
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = Mock(stdout="Everything is OK")

        assert await get_smartctl_args(context, "sda", "") == ["/dev/sda"]
