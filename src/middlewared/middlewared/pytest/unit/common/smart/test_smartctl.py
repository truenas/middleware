import subprocess

from mock import Mock, patch
import pytest

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
                "driver": "sd",
                "controller_id": 17,
                "bus": 0,
                "channel_no": 0,
                "lun_id": 0,
            },
        },
        enterprise_hardware=False,
    )
    stdout = "/dev/sda: Unknown USB bridge [0x0930:0x6544 (0x100)]\nPlease specify device type with the -d option."
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = Mock(stdout=stdout)
        assert await get_smartctl_args(context, "sda", "") == ["/dev/sda", "-d", "sat"]

    run.assert_called_once_with(
        ["smartctl", "/dev/sda", "-i"], stderr=subprocess.STDOUT, check=False, encoding="utf8", errors="ignore"
    )


@pytest.mark.asyncio
async def test_get_disk__generic():
    context = SMARTCTX(
        devices={
            "sda": {
                "driver": "sd",
                "controller_id": 17,
                "bus": 0,
                "channel_no": 0,
                "lun_id": 0,
            },
        },
        enterprise_hardware=False,
    )
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = Mock(stdout="Everything is OK")

        assert await get_smartctl_args(context, "sda", "") == ["/dev/sda"]
