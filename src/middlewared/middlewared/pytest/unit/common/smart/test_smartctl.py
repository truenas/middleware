import asyncio
import subprocess

from mock import Mock, patch
import pytest

from middlewared.common.smart.smartctl import get_smartctl_args


@pytest.mark.asyncio
async def test__get_smartctl_args__arcmsr():
    assert await get_smartctl_args("ada0", {
        "driver": "arcmsrX",
        "controller_id": 1000,
        "bus": 0,
        "channel_no": 100,
        "lun_id": 10,
    }) == ["/dev/arcmsr1000", "-d", "areca,811"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x():
    assert await get_smartctl_args("ada0", {
        "driver": "rr274x_3x",
        "controller_id": 1,
        "bus": 0,
        "channel_no": 2,
        "lun_id": 10,
    }) == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x__1():
    assert await get_smartctl_args("ada0", {
        "driver": "rr274x_3x",
        "controller_id": 1,
        "bus": 0,
        "channel_no": 18,
        "lun_id": 10,
    }) == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x__2():
    assert await get_smartctl_args("ada0", {
        "driver": "rr274x_3x",
        "controller_id": 1,
        "bus": 0,
        "channel_no": 10,
        "lun_id": 10,
    }) == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__hpt():
    assert await get_smartctl_args("ada0", {
        "driver": "hptX",
        "controller_id": 1,
        "bus": 0,
        "channel_no": 2,
        "lun_id": 10,
    }) == ["/dev/hptX", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__ciss():
    assert await get_smartctl_args("ada0", {
        "driver": "cissX",
        "controller_id": 1,
        "bus": 0,
        "channel_no": 2,
        "lun_id": 10,
    }) == ["/dev/cissX1", "-d", "cciss,2"]


@pytest.mark.asyncio
async def test__get_smartctl_args__twa():
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = asyncio.Future()
        run.return_value.set_result(Mock(stdout="p28 u1\np29 u2"))

        assert await get_smartctl_args("ada0", {
            "driver": "twaX",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 2,
            "lun_id": 10,
        }) == ["/dev/twaX1", "-d", "3ware,29"]

        run.assert_called_once_with(
            ["/usr/local/sbin/tw_cli", f"/c1", "show"],
            encoding="utf8",
        )


@pytest.mark.asyncio
async def test_get_disk__unknown_usb_bridge():
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = asyncio.Future()
        run.return_value.set_result(Mock(stdout="/dev/da0: Unknown USB bridge [0x0930:0x6544 (0x100)]\n"
                                                "Please specify device type with the -d option."))

        assert await get_smartctl_args("ada0", {
            "driver": "ata",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 2,
            "lun_id": 10,
        }) == ["/dev/ada0", "-d", "sat"]

        run.assert_called_once_with(["smartctl", "-i", "/dev/ada0"], stderr=subprocess.STDOUT, check=False,
                                    encoding="utf8")


@pytest.mark.asyncio
async def test_get_disk__generic():
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = asyncio.Future()
        run.return_value.set_result(Mock(stdout="Everything is OK"))

        assert await get_smartctl_args("ada0", {
            "driver": "ata",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 2,
            "lun_id": 10,
        }) == ["/dev/ada0"]
