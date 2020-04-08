import asyncio
import subprocess

from mock import Mock, patch
import pytest

from middlewared.common.smart.smartctl import get_smartctl_args
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test__get_smartctl_args__disk_nonexistent():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
        assert await get_smartctl_args(None, {}, "ada0") is None


@pytest.mark.asyncio
async def test__get_smartctl_args__nvd():
    with patch("middlewared.common.smart.smartctl.get_nsid", Mock(return_value="nvme1")):
        with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
            assert await get_smartctl_args(Middleware(), {}, "nvd0") == ["/dev/nvme1"]


@pytest.mark.asyncio
async def test__get_smartctl_args__nvme():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", True):
        assert await get_smartctl_args(Middleware(), {}, "nvme0n1") == ["/dev/nvme0n1", "-d", "nvme"]


@pytest.mark.asyncio
async def test__get_smartctl_args__nvd_ioctl_failed():
    with patch("middlewared.common.smart.smartctl.get_nsid", Mock(side_effect=IOError())):
        with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
            assert await get_smartctl_args(Middleware(), {}, "nvd0") is None


@pytest.mark.parametrize("enclosure,dev", [
    (811, "areca,811"),
    ("811/2", "areca,811/2"),
])
@pytest.mark.asyncio
async def test__get_smartctl_args__arcmsr(enclosure, dev):
    async def annotate_devices_with_areca_dev_id(devices):
        for v in devices.values():
            v["areca_dev_id"] = enclosure

    with patch("middlewared.common.smart.smartctl.annotate_devices_with_areca_dev_id",
               annotate_devices_with_areca_dev_id):
        with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
            assert await get_smartctl_args(None, {"ada0": {
                "driver": "arcmsrX",
                "controller_id": 1000,
                "bus": 0,
                "channel_no": 100,
                "lun_id": 10,
            }}, "ada0") == ["/dev/arcmsr1000", "-d", dev]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
        assert await get_smartctl_args(None, {"ada0": {
            "driver": "rr274x_3x",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 2,
            "lun_id": 10,
        }}, "ada0") == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x__1():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
        assert await get_smartctl_args(None, {"ada0": {
            "driver": "rr274x_3x",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 18,
            "lun_id": 10,
        }}, "ada0") == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__rr274x_3x__2():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
        assert await get_smartctl_args(None, {"ada0": {
            "driver": "rr274x_3x",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 10,
            "lun_id": 10,
        }}, "ada0") == ["/dev/rr274x_3x", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__hpt():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
        assert await get_smartctl_args(None, {"ada0": {
            "driver": "hptX",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 2,
            "lun_id": 10,
        }}, "ada0") == ["/dev/hptX", "-d", "hpt,2/3"]


@pytest.mark.asyncio
async def test__get_smartctl_args__ciss():
    with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
        assert await get_smartctl_args(None, {"ada0": {
            "driver": "cissX",
            "controller_id": 1,
            "bus": 0,
            "channel_no": 2,
            "lun_id": 10,
        }}, "ada0") == ["/dev/cissX1", "-d", "cciss,2"]


@pytest.mark.asyncio
async def test__get_smartctl_args__twa():
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = asyncio.Future()
        run.return_value.set_result(Mock(stdout="p28 u1\np29 u2"))

        with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
            assert await get_smartctl_args(None, {"ada0": {
                "driver": "twaX",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            }}, "ada0") == ["/dev/twaX1", "-d", "3ware,29"]

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

        with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
            assert await get_smartctl_args(None, {"ada0": {
                "driver": "ata",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            }}, "ada0") == ["/dev/ada0", "-d", "sat"]

        run.assert_called_once_with(["smartctl", "/dev/ada0", "-i"], stderr=subprocess.STDOUT, check=False,
                                    encoding="utf8", errors="ignore")


@pytest.mark.asyncio
async def test_get_disk__generic():
    with patch("middlewared.common.smart.smartctl.run") as run:
        run.return_value = asyncio.Future()
        run.return_value.set_result(Mock(stdout="Everything is OK"))

        with patch("middlewared.common.smart.smartctl.osc.IS_LINUX", False):
            assert await get_smartctl_args(None, {"ada0": {
                "driver": "ata",
                "controller_id": 1,
                "bus": 0,
                "channel_no": 2,
                "lun_id": 10,
            }}, "ada0") == ["/dev/ada0"]
