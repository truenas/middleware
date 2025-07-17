"""Test WWN/LUNID handling in DiskEntry.

These tests validate that DiskEntry.lunid properly handles WWN values
to match udev's ID_WWN behavior. For NAA/0x/eui WWNs we strip the prefix
and return first 16 hex chars if applicable. For t10 identifiers lunid
is None (udev doesn't use them for ID_WWN).
"""
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from middlewared.utils.disks_.disk_class import DiskEntry


@pytest.fixture
def mock_sysfs(tmp_path):
    """
    Build an in-memory /sys/block tree and patch `open`
    so DiskEntry reads from it transparently.
    """
    @contextmanager
    def _mock(files: dict[str, bytes | str]):
        # Write files to temporary directory
        for rel_path, data in files.items():
            fpath = tmp_path / "sys" / "block" / rel_path
            fpath.parent.mkdir(parents=True, exist_ok=True)

            if isinstance(data, (bytes, bytearray)):
                fpath.write_bytes(data)
            else:
                fpath.write_text(data)

        # Patch builtins.open to redirect /sys/block reads to our temp dir
        import builtins
        original_open = builtins.open

        def mock_open(path, mode='r', *args, **kwargs):
            if "/sys/block/" in str(path):
                # Extract relative path after /sys/block/
                rel_path = str(path).split("/sys/block/", 1)[1]
                test_path = tmp_path / "sys" / "block" / rel_path
                return original_open(str(test_path), mode, *args, **kwargs)
            return original_open(path, mode, *args, **kwargs)

        with patch('builtins.open', side_effect=mock_open):
            yield

    return _mock


@pytest.mark.parametrize(
    "files,expected",
    [
        # Full 32-character WWN with naa. prefix (should truncate to 16)
        ({"sda/device/wwid": "naa.60014055f10d56d85874876b24dbf26b"},
         "60014055f10d56d8"),

        # Full 32-character WWN with 0x prefix (should truncate to 16)
        ({"sda/device/wwid": "0x60014055f10d56d85874876b24dbf26b"},
         "60014055f10d56d8"),


        # 16-character WWN (no truncation needed)
        ({"sda/device/wwid": "naa.60014055f10d56d8"},
         "60014055f10d56d8"),

        # Shorter WWN (no truncation)
        ({"sda/device/wwid": "naa.12345678"},
         "12345678"),

        # No wwid file
        ({},
         None),

        # Empty wwid
        ({"sda/device/wwid": ""},
         None),

        # WWN with spaces (t10 format - returns None as t10 is not used for ID_WWN)
        ({"sda/device/wwid": "t10.ATA     QEMU HARDDISK                           QM00003"},
         None),

        # WWN from /sys/block/sda/wwid (not device/wwid)
        ({"sda/wwid": "naa.600140596d07f59676146fe9ebe4aed6"},
         "600140596d07f596"),

        # Very long WWN (more than 32 chars after prefix removal)
        ({"sda/device/wwid": "naa." + "a" * 40},
         "a" * 16),

        # Upper-case prefixes (should be handled case-insensitively)
        ({"sda/device/wwid": "NAA.60014055F10D56D85874876B24DBF26B"},
         "60014055f10d56d8"),

        ({"sda/device/wwid": "0X60014055F10D56D85874876B24DBF26B"},
         "60014055f10d56d8"),


        # Non‑hex characters within first 16 → no truncation
        ({"sda/device/wwid": "naa.12345zzzz67890abcde"},
         "12345zzzz67890abcde"),

        # Very short WWN
        ({"sda/device/wwid": "naa.1a2b"},
         "1a2b"),

        # raw 0x prefix shorter than 16 (no truncation)
        ({"sda/device/wwid": "0x6001abc"},
         "6001abc"),

        # mixed-case hex, should lower-case + truncate
        ({"sda/device/wwid": "0x6001ABCDEF1234567890"},
         "6001abcdef123456"),

        # EUI-64 identifier (common for NVMe) - should strip prefix
        ({"sda/device/wwid": "eui.6479a7939a303551"},
         "6479a7939a303551"),

        # EUI-64 with more than 16 hex chars - should truncate
        ({"sda/device/wwid": "eui.6479a7939a3035510123456789abcdef"},
         "6479a7939a303551"),

        # EUI-64 upper case - should lowercase and strip
        ({"sda/device/wwid": "EUI.6479A7939A303551"},
         "6479a7939a303551"),

        # EUI-64 from NVMe wwid file (not device/wwid)
        ({"nvme0n1/wwid": "eui.6479a7939a303551"},
         "6479a7939a303551"),
    ],
)
def test_lunid_truncation(mock_sysfs, files, expected):
    """Test that lunid properly handles various WWN formats.

    Truncation to 16 characters only occurs when those characters are valid hex.
    Non-hex identifiers (like t10 format) are preserved in full.
    """
    with mock_sysfs(files):
        # Use appropriate device name based on the files provided
        if "nvme0n1" in str(files):
            disk = DiskEntry(name="nvme0n1", devpath="/dev/nvme0n1")
        else:
            disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.lunid == expected


def test_lunid_priority_device_over_block(mock_sysfs):
    """Test that device/wwid takes priority over wwid."""
    files = {
        "sda/device/wwid": "naa.60014055f10d56d85874876b24dbf26b",  # 32 chars
        "sda/wwid": "naa.deadbeefdeadbeefdeadbeefdeadbeef",         # different value
    }
    with mock_sysfs(files):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        # Should use device/wwid and truncate to 16
        assert disk.lunid == "60014055f10d56d8"


def test_lunid_cached_property(mock_sysfs):
    """Test that lunid is only read once (cached_property)."""
    files = {"sda/device/wwid": "naa.60014055f10d56d85874876b24dbf26b"}

    with mock_sysfs(files):
        disk = DiskEntry(name="sda", devpath="/dev/sda")

        # First access
        lunid1 = disk.lunid
        assert lunid1 == "60014055f10d56d8"

        # Second access should return cached value
        with patch('builtins.open', return_value=None):
            lunid2 = disk.lunid
            assert lunid2 == "60014055f10d56d8"
            assert lunid1 is lunid2  # Same object reference


def test_lunid_lowercase(mock_sysfs):
    """Test that lunid always returns lowercase values."""
    files = {"sda/device/wwid": "NAA.60014055F10D56D8"}
    with mock_sysfs(files):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.lunid == "60014055f10d56d8"
        # Verify all characters are lowercase
        assert disk.lunid == disk.lunid.lower()


def test_lunid_matches_udev_behavior(mock_sysfs):
    """
    Test that our implementation matches udev's behavior.

    udev splits WWN into:
    - ID_WWN: First 16 hex chars (what we return for valid hex WWNs)
    - ID_WWN_VENDOR_EXTENSION: Next 16 hex chars
    - ID_WWN_WITH_EXTENSION: Full 32 chars

    Note: Truncation only occurs for valid hex identifiers.
    """
    # Real example from sdk disk on test system
    full_wwn = "60014055f10d56d85874876b24dbf26b"
    expected_id_wwn = "60014055f10d56d8"
    expected_vendor_ext = "5874876b24dbf26b"

    files = {"sdk/device/wwid": f"naa.{full_wwn}"}
    with mock_sysfs(files):
        disk = DiskEntry(name="sdk", devpath="/dev/sdk")
        assert disk.lunid == expected_id_wwn
        assert len(disk.lunid) == 16
        # Verify it's the first 16 chars of the full WWN
        assert full_wwn.startswith(disk.lunid)
        assert full_wwn[16:] == expected_vendor_ext
