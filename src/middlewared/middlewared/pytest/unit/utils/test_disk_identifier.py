"""Tests for the disk identifier ladder shared by `dev_to_ident` and
`DiskEntry.identifier`, and for the udev property parsers shared by the
`device.get_disks` side (NAS-136915)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from middlewared.plugins.device_.device_info import DeviceService
from middlewared.utils.disks import dev_to_ident, get_disk_serial_from_block_device
from middlewared.utils.disks_.disk_class import DiskEntry
from middlewared.utils.disks_.gpt_parts import PART_TYPES
from middlewared.utils.disks_.identifier import build_identifier, join_serial_lunid
from middlewared.utils.disks_.udev import lunid_from_udev, serial_from_udev

ZFS_GUID = next(guid for guid, name in PART_TYPES.items() if name == "ZFS")
PART_UUID = "b9253137-a0a4-11ec-b194-3cecef615fde"

# udev properties and sysfs contents as measured on the named systems
SAS_HGST = {
    "ID_BUS": "scsi",
    "ID_SCSI_SERIAL": "5QG7BWGF",
    "ID_SERIAL_SHORT": "5000cca2b00d6cdc",
    "ID_SERIAL": "35000cca2b00d6cdc",
    "ID_WWN": "0x5000cca2b00d6cdc",
}
SAS_HGST_SYSFS = {
    "sda/device/vpd_pg80": b"\x00\x80\x00\x10        5QG7BWGF",
    "sda/device/wwid": "naa.5000cca2b00d6cdc\n",
}
NVME_IX = {
    "ID_SERIAL_SHORT": "511250113257000151",
    "ID_SERIAL": "iXTSUN4SCEQ480R1_511250113257000151_1",
    "ID_WWN": "eui.6479a7a14a2002a3",
}
NVME_IX_SYSFS = {
    "nvme0n1/device/serial": "511250113257000151  \n",
    "nvme0n1/wwid": "eui.6479a7a14a2002a3\n",
}
# ata_id sets no ID_SCSI_SERIAL, and libata synthesizes VPD page 0x80 from the same ATA serial
SATA_QEMU = {"ID_BUS": "ata", "ID_SERIAL_SHORT": "mzgzzuQN", "ID_SERIAL": "QEMU_HARDDISK_mzgzzuQN"}
SATA_QEMU_SYSFS = {
    "sda/device/vpd_pg80": b"\x00\x80\x00\x14mzgzzuQN            ",
    "sda/device/wwid": "t10.ATA     QEMU HARDDISK                       \n",
}
SCSI_DEBUG = {
    "ID_BUS": "scsi",
    "ID_SCSI_SERIAL": "2000",
    "ID_SERIAL_SHORT": "33333330000007d0",
    "ID_SERIAL": "333333330000007d0",
    "ID_WWN": "0x33333330000007d0",
}
SCSI_DEBUG_SYSFS = {
    "sda/device/vpd_pg80": b"\x00\x80\x00\x042000",
    "sda/device/wwid": "naa.33333330000007d0\n",
}


def block_device(name: str, properties: dict[str, str]) -> MagicMock:
    """What `pyudev.Devices.from_name` returns, as far as the identity code reads it."""
    device = MagicMock()
    device.sys_name = name
    device.properties = properties
    device.children = []
    return device


@pytest.mark.parametrize(
    "serial_lunid,serial,uuid,expected",
    [
        ("5QG7BWGF_5000cca2b00d6cdc", "5QG7BWGF", None, "{serial_lunid}5QG7BWGF_5000cca2b00d6cdc"),
        (None, "5QG7BWGF", None, "{serial}5QG7BWGF"),
        (None, None, PART_UUID, f"{{uuid}}{PART_UUID}"),
        (None, None, None, "{devicename}sda"),
        ("", "", None, "{devicename}sda"),
    ],
)
def test_build_identifier_ladder(serial_lunid, serial, uuid, expected):
    assert build_identifier("sda", serial_lunid, serial, lambda: uuid) == expected


@pytest.mark.parametrize(
    "serial,lunid,expected",
    [
        ("5QG7BWGF", "5000cca2b00d6cdc", "5QG7BWGF_5000cca2b00d6cdc"),
        ("5QG7BWGF", None, None),
        (None, "5000cca2b00d6cdc", None),
        ("", "5000cca2b00d6cdc", None),
        (None, None, None),
    ],
)
def test_join_serial_lunid(serial, lunid, expected):
    assert join_serial_lunid(serial, lunid) == expected


@pytest.mark.parametrize(
    "serial_lunid,serial",
    [
        ("5QG7BWGF_5000cca2b00d6cdc", "5QG7BWGF"),
        (None, "5QG7BWGF"),
    ],
)
def test_partitions_not_read_when_serial_known(serial_lunid, serial):
    """Reading partitions opens the block device, which would happen on every
    disk-stats tick if the identifier did it needlessly."""
    zfs_partition_uuid = Mock()
    build_identifier("sda", serial_lunid, serial, zfs_partition_uuid)
    zfs_partition_uuid.assert_not_called()


def test_partitions_read_once_when_no_serial():
    zfs_partition_uuid = Mock(return_value=PART_UUID)
    assert build_identifier("sda", None, None, zfs_partition_uuid) == f"{{uuid}}{PART_UUID}"
    zfs_partition_uuid.assert_called_once_with()


@pytest.mark.parametrize(
    "files,expected",
    [
        (SAS_HGST_SYSFS, "{serial_lunid}5QG7BWGF_5000cca2b00d6cdc"),
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x085QG7BWGF"}, "{serial}5QG7BWGF"),
    ],
)
def test_disk_entry_does_not_read_partitions_when_serial_known(mock_sysfs, files, expected):
    with mock_sysfs(files):
        with patch.object(DiskEntry, "partitions") as partitions:
            assert DiskEntry(name="sda", devpath="/dev/sda").identifier == expected

    partitions.assert_not_called()


def test_disk_entry_reads_partitions_when_no_serial(mock_sysfs):
    part = SimpleNamespace(partition_type_guid=ZFS_GUID, unique_partition_guid=PART_UUID)
    with mock_sysfs({}):
        with patch.object(DiskEntry, "partitions", return_value=(part,)) as partitions:
            assert DiskEntry(name="sda", devpath="/dev/sda").identifier == f"{{uuid}}{PART_UUID}"

    partitions.assert_called_once()


def test_disk_entry_device_name_when_nothing_identifies_it(mock_sysfs):
    with mock_sysfs({}):
        with patch.object(DiskEntry, "partitions", return_value=None):
            assert DiskEntry(name="sda", devpath="/dev/sda").identifier == "{devicename}sda"


@pytest.mark.parametrize(
    "properties,expected",
    [
        # scsi_id sets all three, and only ID_SCSI_SERIAL is the unit serial number
        (SAS_HGST, "5QG7BWGF"),
        (NVME_IX, "511250113257000151"),
        (SATA_QEMU, "mzgzzuQN"),
        ({"ID_SERIAL": "vdserial01"}, "vdserial01"),  # virtio
        # an empty value is skipped rather than returned
        ({"ID_SCSI_SERIAL": "   ", "ID_SERIAL_SHORT": "6002248079f9f66f"}, "6002248079f9f66f"),
        ({}, None),
    ],
)
def test_serial_from_udev_key_precedence(properties, expected):
    assert serial_from_udev(properties) == expected


@pytest.mark.parametrize(
    "properties,expected",
    [
        ({"ID_WWN": "0x5000cca2b00d6cdc"}, "5000cca2b00d6cdc"),  # scsi_id
        ({"ID_WWN": "eui.6479a7a14a2002a3"}, "6479a7a14a2002a3"),  # nvme
        ({"ID_WWN": "5000cca2b00d6cdc"}, "5000cca2b00d6cdc"),
        ({"ID_WWN": "0x"}, None),
        ({"ID_WWN": ""}, None),
        ({}, None),
    ],
)
def test_lunid_from_udev_strips_prefixes(properties, expected):
    assert lunid_from_udev(properties) == expected


def test_device_get_lunid_prefers_udev(mock_sysfs):
    device = block_device("sda", {"ID_WWN": "0x5000ccaffffffffe"})
    with mock_sysfs({"sda/device/wwid": "naa.5000cca2b00d6cdc"}):
        assert DeviceService(Mock()).get_lunid(device) == "5000ccaffffffffe"


def test_device_get_lunid_falls_back_to_sysfs(mock_sysfs):
    """NAS-137807: an EUI-64 wwid that udev did not expose as ID_WWN."""
    device = block_device("sda", {"ID_BUS": "scsi", "ID_SCSI_SERIAL": "S1"})
    with mock_sysfs({"sda/device/wwid": "eui.0011223344556677"}):
        assert DeviceService(Mock()).get_lunid(device) == "0011223344556677"


@pytest.mark.parametrize(
    "name,udev,sysfs,expected",
    [
        ("sda", SAS_HGST, SAS_HGST_SYSFS, "{serial_lunid}5QG7BWGF_5000cca2b00d6cdc"),
        ("nvme0n1", NVME_IX, NVME_IX_SYSFS, "{serial_lunid}511250113257000151_6479a7a14a2002a3"),
        ("sda", SATA_QEMU, SATA_QEMU_SYSFS, "{serial}mzgzzuQN"),
        ("sda", SCSI_DEBUG, SCSI_DEBUG_SYSFS, "{serial_lunid}2000_33333330000007d0"),
    ],
)
def test_sync_path_and_disk_entry_agree_on_shipped_hardware(mock_sysfs, name, udev, sysfs, expected):
    """The identifier `disk.sync_all` stores must equal the one
    `DiskEntry.identifier` computes for the same disk.

    They are separate reads, udev on the sync path and sysfs in DiskEntry,
    but they agree on every disk class we ship: libata synthesizes VPD page
    0x80 from the same ATA serial `ata_id` reads, scsi_id and the kernel read
    the same VPD pages, and the NVMe rules copy the sysfs attributes verbatim.
    The sync path is assembled here the way `get_disk_details` builds the
    dict `dev_to_ident` reads.
    """
    device = block_device(name, udev)
    with mock_sysfs(sysfs):
        serial = get_disk_serial_from_block_device(device)
        lunid = DeviceService(Mock()).get_lunid(device)
        sys_disks = {
            name: {"serial": serial, "lunid": lunid, "serial_lunid": join_serial_lunid(serial, lunid), "parts": []}
        }
        via_sync_path = dev_to_ident(name, sys_disks)
        via_disk_entry = DiskEntry(name=name, devpath=f"/dev/{name}").identifier

    assert via_sync_path == via_disk_entry == expected
