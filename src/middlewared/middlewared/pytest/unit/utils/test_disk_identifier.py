"""Tests for the disk identifier ladder shared by `dev_to_ident` and
`DiskEntry.identifier`, the udev serial parser shared by the
`device.get_disks` side, and the udev fallback `DiskEntry` takes for a disk
sysfs has no serial for (NAS-136915)."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
import pyudev

from middlewared.plugins.device_.device_info import DeviceService
from middlewared.utils.disks import dev_to_ident, get_disk_lunid_from_block_device
from middlewared.utils.disks_.disk_class import DiskEntry
from middlewared.utils.disks_.gpt_parts import PART_TYPES
from middlewared.utils.disks_.udev import serial_from_udev, udev_fallback_identity

ZFS_GUID = next(guid for guid, name in PART_TYPES.items() if name == "ZFS")
EFI_GUID = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
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
# A SCSI disk with VPD page 0x83 but no page 0x80 (a Hyper-V virtual disk): sysfs
# has no serial at all, and scsi_id put the page 0x83 NAA designator in ID_SERIAL_SHORT
SCSI_NO_PAGE_80 = {
    "ID_BUS": "scsi",
    "ID_SERIAL_SHORT": "6002248079f9f66f426ea82fb0957801",
    "ID_SERIAL": "36002248079f9f66f426ea82fb0957801",
    "ID_WWN": "0x6002248079f9f66f",
}
SCSI_NO_PAGE_80_SYSFS = {"sda/device/wwid": "naa.6002248079f9f66f426ea82fb0957801\n"}
# A SATA drive in a usb-storage enclosure whose bridge passes ATA commands through:
# usb-storage skips VPD pages, so sysfs has neither serial nor wwid, while ata_id
# read both the serial and the WWN from the drive itself
USB_ATA = {
    "ID_BUS": "ata",
    "ID_SERIAL_SHORT": "WD-WCC4N5PL7XKV",
    "ID_SERIAL": "WDC_WD40EFRX-68N32N0_WD-WCC4N5PL7XKV",
    "ID_WWN": "0x50014ee2b3a4b5c6",
}
# A single-disk USB enclosure whose bridge does not pass ATA commands through:
# usb_id's serial is the bridge's, which is how the disk table has always
# identified such a disk
USB_BRIDGE = {
    "ID_BUS": "usb",
    "ID_SERIAL_SHORT": "2HC015KJ",
    "ID_SERIAL": "WD_Elements_25A3_2HC015KJ-0:0",
    "ID_INSTANCE": "0:0",
}
# The second slot of a USB card reader: usb_id gives every LUN of one bridge the
# same ID_SERIAL_SHORT and only tells them apart in ID_SERIAL and ID_INSTANCE
USB_CARD_READER_SLOT = {
    "ID_BUS": "usb",
    "ID_SERIAL_SHORT": "000000000101",
    "ID_SERIAL": "Generic_USB_SD_Reader_000000000101-0:1",
    "ID_INSTANCE": "0:1",
}
# ata_id on a drive with no serial prints the bare model and no ID_SERIAL_SHORT
SATA_NO_SERIAL = {"ID_BUS": "ata", "ID_SERIAL": "QEMU_HARDDISK"}


def udev_device(name: str, properties: dict[str, str]) -> MagicMock:
    """A pyudev block device, as far as `get_disk_details` reads it."""
    device = MagicMock()
    device.sys_name = name
    device.device_number = 2048
    device.properties = properties
    device.attributes = {"size": "20971520", "queue/logical_block_size": "512", "queue/rotational": "0"}
    device.parent.properties = {"SUBSYSTEM": "pci", "DRIVER": "ahci", "DEVPATH": "/devices/pci0000:00/0000:00:1f.2"}
    device.children = []
    return device


@contextmanager
def real_udev_fallback(properties: dict[str, str]):
    """Let DiskEntry run the real udev fallback against these properties."""
    device = MagicMock()
    device.properties = properties
    with patch("middlewared.utils.disks_.disk_class.udev_fallback_identity", udev_fallback_identity):
        with patch("middlewared.utils.disks_.udev.pyudev.Context"):
            with patch("middlewared.utils.disks_.udev.pyudev.Devices.from_name", return_value=device):
                yield


@pytest.mark.parametrize(
    "files,expected",
    [
        (SAS_HGST_SYSFS, "{serial_lunid}5QG7BWGF_5000cca2b00d6cdc"),
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x085QG7BWGF"}, "{serial}5QG7BWGF"),
    ],
)
def test_disk_entry_does_not_read_partitions_when_serial_known(mock_sysfs, files, expected):
    """Reading partitions opens the block device, which would happen on every
    disk-stats tick if the identifier did it needlessly."""
    with mock_sysfs(files):
        with patch.object(DiskEntry, "partitions") as partitions:
            assert DiskEntry(name="sda", devpath="/dev/sda").identifier == expected

    partitions.assert_not_called()


def test_disk_entry_reads_partitions_when_no_serial(mock_sysfs):
    """Only a ZFS partition identifies the disk, whatever sits ahead of it."""
    efi = SimpleNamespace(partition_type_guid=EFI_GUID, unique_partition_guid="0f3b7a52-1c2d-4e6f-8a9b-0c1d2e3f4a5b")
    zfs = SimpleNamespace(partition_type_guid=ZFS_GUID, unique_partition_guid=PART_UUID)
    with mock_sysfs({}):
        with patch.object(DiskEntry, "partitions", return_value=(efi, zfs)) as partitions:
            assert DiskEntry(name="sda", devpath="/dev/sda").identifier == f"{{uuid}}{PART_UUID}"

    partitions.assert_called_once()


@pytest.mark.parametrize("name,files", [("sda", SAS_HGST_SYSFS), ("nvme0n1", NVME_IX_SYSFS), ("sda", SATA_QEMU_SYSFS)])
def test_udev_not_consulted_when_sysfs_has_a_serial(mock_sysfs, name, files):
    """The fallback must cost nothing on the hardware we ship, where sysfs
    always has a serial: udev is not looked up at all, not even for a lunid
    sysfs lacks (the t10 wwid of the SATA case)."""
    with mock_sysfs(files):
        with patch("middlewared.utils.disks_.disk_class.udev_fallback_identity") as udev:
            DiskEntry(name=name, devpath=f"/dev/{name}").identifier

    udev.assert_not_called()


def test_udev_serial_used_when_sysfs_has_none(mock_sysfs):
    """A disk with no VPD page 0x80 gets the serial udev resolved, and so a
    stable identifier without reading its partition table."""
    with mock_sysfs(SCSI_NO_PAGE_80_SYSFS):
        with real_udev_fallback(SCSI_NO_PAGE_80):
            with patch.object(DiskEntry, "partitions") as partitions:
                disk = DiskEntry(name="sda", devpath="/dev/sda")
                assert disk.serial == "6002248079f9f66f426ea82fb0957801"
                assert disk.identifier == "{serial_lunid}6002248079f9f66f426ea82fb0957801_6002248079f9f66f"

    partitions.assert_not_called()


def test_udev_wwn_used_when_the_serial_came_from_udev(mock_sysfs):
    """usb-storage skips VPD pages, so such a disk has no wwid in sysfs either;
    the WWN ata_id read from the drive comes from the same udev lookup."""
    with mock_sysfs({}):
        with real_udev_fallback(USB_ATA):
            disk = DiskEntry(name="sda", devpath="/dev/sda")
            assert disk.lunid == "50014ee2b3a4b5c6"
            assert disk.identifier == "{serial_lunid}WD-WCC4N5PL7XKV_50014ee2b3a4b5c6"


def test_udev_fallback_ignores_a_model_only_id_serial():
    """ID_SERIAL is the bare model for a drive with no serial, so it must not
    reach the fallback, or every serial-less drive of one model would share
    an identifier."""
    with real_udev_fallback(SATA_NO_SERIAL):
        assert udev_fallback_identity("sda") == (None, None)


def test_udev_fallback_keeps_a_bridge_serial_for_its_first_lun_only():
    """usb_id's serial is the bridge's, shared by every LUN behind it. The
    first LUN keeps it, as the disk table always has for a single-disk
    enclosure; a card reader's further slots must not collapse into it."""
    with real_udev_fallback(USB_BRIDGE):
        assert udev_fallback_identity("sda") == ("2HC015KJ", None)

    with real_udev_fallback(USB_CARD_READER_SLOT):
        assert udev_fallback_identity("sdb") == (None, None)


def test_udev_fallback_none_when_udev_has_no_record():
    with patch(
        "middlewared.utils.disks_.udev.pyudev.Devices.from_name",
        side_effect=pyudev.DeviceNotFoundByNameError("block", "sda"),
    ):
        assert udev_fallback_identity("sda") == (None, None)


def test_udev_fallback_skips_an_undecodable_serial():
    """pyudev decodes strictly, so a serial holding a byte that is not UTF-8
    raises from `get`. One such disk must not take down the disk-stats tick."""

    def get(key, default=None):
        if key == "ID_SCSI_SERIAL":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return {"ID_BUS": "scsi", "ID_SERIAL_SHORT": "5000cca2b00d6cdc"}.get(key, default)

    device = MagicMock()
    device.properties.get.side_effect = get
    with patch("middlewared.utils.disks_.udev.pyudev.Devices.from_name", return_value=device):
        assert udev_fallback_identity("sda") == ("5000cca2b00d6cdc", None)


@pytest.mark.parametrize(
    "properties,expected",
    [
        ({"ID_SERIAL": "vdserial01"}, "vdserial01"),  # virtio sets only ID_SERIAL
        # an empty value is skipped rather than returned
        ({"ID_SCSI_SERIAL": "   ", "ID_SERIAL_SHORT": "6002248079f9f66f"}, "6002248079f9f66f"),
        ({}, None),
    ],
)
def test_serial_from_udev_key_precedence(properties, expected):
    assert serial_from_udev(properties) == expected


def test_lunid_from_block_device_prefers_udev(mock_sysfs):
    device = udev_device("sda", {"ID_WWN": "0x5000ccaffffffffe"})
    with mock_sysfs({"sda/device/wwid": "naa.5000cca2b00d6cdc"}):
        assert get_disk_lunid_from_block_device(device) == "5000ccaffffffffe"


def test_lunid_from_block_device_falls_back_to_sysfs(mock_sysfs):
    """NAS-137807: an EUI-64 wwid that udev did not expose as ID_WWN."""
    device = udev_device("sda", {"ID_BUS": "scsi", "ID_SCSI_SERIAL": "S1"})
    with mock_sysfs({"sda/device/wwid": "eui.0011223344556677"}):
        assert get_disk_lunid_from_block_device(device) == "0011223344556677"


@pytest.mark.parametrize(
    "name,udev,sysfs,expected",
    [
        ("sda", SAS_HGST, SAS_HGST_SYSFS, "{serial_lunid}5QG7BWGF_5000cca2b00d6cdc"),
        ("nvme0n1", NVME_IX, NVME_IX_SYSFS, "{serial_lunid}511250113257000151_6479a7a14a2002a3"),
        ("sda", SATA_QEMU, SATA_QEMU_SYSFS, "{serial}mzgzzuQN"),
        # only through the udev fallback, since sysfs has no serial for these disks
        (
            "sda",
            SCSI_NO_PAGE_80,
            SCSI_NO_PAGE_80_SYSFS,
            "{serial_lunid}6002248079f9f66f426ea82fb0957801_6002248079f9f66f",
        ),
        ("sda", USB_ATA, {}, "{serial_lunid}WD-WCC4N5PL7XKV_50014ee2b3a4b5c6"),
        ("sda", USB_BRIDGE, {}, "{serial}2HC015KJ"),
    ],
)
def test_sync_path_and_disk_entry_agree(mock_sysfs, name, udev, sysfs, expected):
    """The identifier `disk.sync_all` stores must equal the one
    `DiskEntry.identifier` computes for the same disk.

    They are separate reads, udev on the sync path and sysfs in DiskEntry,
    but they agree on every disk class we ship: libata synthesizes VPD page
    0x80 from the same ATA serial `ata_id` reads, scsi_id and the kernel read
    the same VPD pages, and the NVMe rules copy the sysfs attributes verbatim.
    The sync path is `device.get_disks` building a dict with `get_disk_details`
    and `dev_to_ident` reading it, so that is what runs here.
    """
    device = udev_device(name, udev)
    with mock_sysfs(sysfs):
        with real_udev_fallback(udev):
            sys_disks = {name: DeviceService(Mock()).get_disk_details(None, device)}
            via_sync_path = dev_to_ident(name, sys_disks)
            via_disk_entry = DiskEntry(name=name, devpath=f"/dev/{name}").identifier

    assert via_sync_path == via_disk_entry == expected
