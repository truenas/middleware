"""Tests for the disk identifier ladder shared by `dev_to_ident` and
`DiskEntry.identifier` (NAS-136915)."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from middlewared.utils.disks_.disk_class import DiskEntry
from middlewared.utils.disks_.gpt_parts import PART_TYPES
from middlewared.utils.disks_.identifier import build_identifier, join_serial_lunid

ZFS_GUID = next(guid for guid, name in PART_TYPES.items() if name == "ZFS")
PART_UUID = "b9253137-a0a4-11ec-b194-3cecef615fde"


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
        (
            {"sda/device/vpd_pg80": b"\x00\x80\x00\x085QG7BWGF", "sda/device/wwid": "naa.5000cca2b00d6cdc"},
            "{serial_lunid}5QG7BWGF_5000cca2b00d6cdc",
        ),
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
