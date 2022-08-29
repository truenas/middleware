import subprocess

from mock import Mock, patch
import pytest

from middlewared.common.smart.smartctl import get_smartctl_args, SMARTCTX


@pytest.mark.asyncio
async def test__get_smartctl_args__disk_nonexistent():
    context = SMARTCTX(devices={}, enterprise_hardware=False)
    assert await get_smartctl_args(context, "ada0", "") is None


@pytest.mark.asyncio
async def test__get_smartctl_args__nvme():
    context = SMARTCTX(devices={}, enterprise_hardware=False)
    assert await get_smartctl_args(context, "nvme0n1", "") == ["/dev/nvme0n1", "-d", "nvme"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "rr274x_3x",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            }
        },
        enterprise_hardware=False,
    )
    assert await get_smartctl_args(context, "ada0", "") == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x__1():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "rr274x_3x",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 18,
                "lun_id": 10,
            },
        },
        enterprise_hardware=False,
    )
    assert await get_smartctl_args(context, "ada0", "") == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x__2():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "rr274x_3x",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 10,
                "lun_id": 10,
            },
        },
        enterprise_hardware=False,
    )
    assert await get_smartctl_args(context, "ada0", "") == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__hpt():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "hptx",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            },
        },
        enterprise_hardware=False,
    )
    assert await get_smartctl_args(context, "ada0", "") == ["/dev/hptX", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__twa():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "twaX",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            },
        },
        enterprise_hardware=False,
    )
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = Mock(stdout="p28 u1\np29 u2")

        assert await get_smartctl_args(context, "ada0", "") == ["/dev/twaX1", "-d", "3ware,29"]

        run.assert_called_once_with(["/usr/local/sbin/tw_cli", "/c1", "show"], encoding="utf8")


@pytest.mark.asyncio
async def test_get_disk__unknown_usb_bridge():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "ata",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            },
        },
        enterprise_hardware=False,
    )
    stdout = "/dev/da0: Unknown USB bridge [0x0930:0x6544 (0x100)]\nPlease specify device type with the -d option."
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = Mock(stdout=stdout)
        assert await get_smartctl_args(context, "ada0", "") == ["/dev/ada0", "-d", "sat"]

    run.assert_called_once_with(
        ["smartctl", "/dev/ada0", "-i"], stderr=subprocess.STDOUT, check=False, encoding="utf8", errors="ignore"
    )


@pytest.mark.asyncio
async def test_get_disk__generic():
    context = SMARTCTX(
        devices={
            "ada0": {
                "driver": "ata",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            },
        },
        enterprise_hardware=False,
    )
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = Mock(stdout="Everything is OK")

        assert await get_smartctl_args(context, "ada0", "") == ["/dev/ada0"]
