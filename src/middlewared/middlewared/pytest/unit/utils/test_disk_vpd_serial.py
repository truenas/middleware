"""Test VPD page 0x80 serial number parsing.

These tests validate the DiskEntry.serial property's handling of SCSI VPD
(Vital Product Data) page 0x80, which contains disk serial numbers. The tests
ensure correct parsing of the 4-byte header structure and proper extraction
of serial data, guarding against regressions in header parsing.

Per SCSI specifications, VPD page 0x80 (Unit Serial Number) is limited to
255 bytes of serial data, using a single-byte length field at byte 3.
"""
import builtins
from collections import Counter
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from middlewared.utils.disks_.disk_class import DiskEntry


@contextmanager
def count_opens():
    """
    Context manager that counts how many times any /sys/block/ file
    is opened during the `with` body.
    """
    counter = Counter()
    real_open = builtins.open

    def _counting_open(path, mode='r', *a, **kw):
        if "/sys/block/" in str(path):
            counter[str(path)] += 1
        return real_open(path, mode, *a, **kw)

    with patch("builtins.open", side_effect=_counting_open):
        yield counter


@pytest.fixture
def mock_sysfs(tmp_path):
    """
    Build an in-memory /sys/block tree and patch `open`
    so DiskEntry reads from it transparently.

    Usage:
        files = {
            "sda/device/vpd_pg80": b"...",
            "sda/device/serial": "SER123",
        }
        with mock_sysfs(files):
            disk = DiskEntry(name="sda", devpath="/dev/sda")
            ...
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
        original_open = builtins.open

        def mock_open(path, mode='r', *args, **kwargs):
            if "/sys/block/" in str(path):
                # Extract relative path after /sys/block/
                rel_path = str(path).split("/sys/block/", 1)[1]
                test_path = tmp_path / "sys" / "block" / rel_path
                return original_open(str(test_path), mode, *args, **kwargs)
            return original_open(path, mode, *args, **kwargs)

        # Expose original handle for count_opens to use
        mock_open.__wrapped__ = original_open

        with patch('builtins.open', side_effect=mock_open):
            yield

    return _mock


@pytest.mark.parametrize(
    "files,expected",
    [
        # Standard VPD page 0x80 cases
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x25" + b"68d6bfe1-4b65-40c4-8bd8-87e377870f18"},
         "68d6bfe1-4b65-40c4-8bd8-87e377870f18"),

        # Short serial
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x0d" + b"ha001_c1_os00"},
         "ha001_c1_os00"),

        # Zero length
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x00"},
         None),

        # Non-zero byte 2 (reserved, should still work)
        ({"sda/device/vpd_pg80": b"\x00\x80\x01\x10" + b"A" * 0x10},
         "A" * 0x10),

        # Maximum length (255 bytes)
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\xff" + b"A" * 0xff},
         "A" * 0xff),

        # Length exceeds buffer
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x64" + b"SHORT_SERIAL_12345"},
         "SHORT_SERIAL_12345"),

        # UTF-8 characters (decode with errors='ignore' strips non-ASCII)
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x06" + b"\xc2\xa9UTF8"},
         "UTF8"),

        # Regular serial file takes precedence
        ({"sda/device/serial": "REGULAR", "sda/device/vpd_pg80": b"\x00\x80\x00\x04TEST"},
         "REGULAR"),

        # Corrupted VPD header (less than 4 bytes)
        ({"sda/device/vpd_pg80": b"\x00\x80"},
         None),

        # Empty VPD file
        ({"sda/device/vpd_pg80": b""},
         None),

        # VPD with null bytes in serial (rstrip removes trailing nulls)
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x0a" + b"TEST\x00\x00MORE"},
         "TEST\x00\x00MORE"),

        # VPD with trailing null bytes
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x08" + b"SERIAL\x00\x00"},
         "SERIAL"),

        # Non-ASCII bytes (should be ignored)
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x10" + b"TEST\x00\x01\x02SERIAL\x00\x03\x04\x05"},
         "TEST\x00\x01\x02SERIAL\x00\x03\x04"),

        # VPD with trailing spaces that should be stripped
        ({"sda/device/vpd_pg80": b"\x00\x80\x00\x08" + b"SERIAL  "},
         "SERIAL"),

        # Legacy device with non-zero byte 2 but length in byte 3 (backward compatibility)
        ({"sda/device/vpd_pg80": b"\x00\x80\xff\x10" + b"LEGACY_SERIAL123"},
         "LEGACY_SERIAL123"),
    ],
)
def test_vpd_pg80_variants(mock_sysfs, files, expected):
    """Test various VPD page 0x80 parsing scenarios."""
    with mock_sysfs(files):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.serial == expected


def test_serial_whitespace_stripped(mock_sysfs):
    """Test that serial numbers are stripped of whitespace."""
    files = {"sda/device/serial": "        3FJ1U1HT        "}
    with mock_sysfs(files):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.serial == "3FJ1U1HT"


def test_serial_trailing_newline(mock_sysfs):
    """Test that trailing newlines are stripped."""
    files = {"sda/device/serial": "SERIAL123\n"}
    with mock_sysfs(files):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.serial == "SERIAL123"


def test_no_serial_returns_none(mock_sysfs):
    """Test that disks without serial numbers return None."""
    files = {}  # No serial sources
    with mock_sysfs(files):
        disk = DiskEntry(name="vda", devpath="/dev/vda")
        assert disk.serial is None


def test_pmem_uuid_fallback(mock_sysfs):
    """Test fallback to UUID for pmem devices."""
    files = {"pmem0/uuid": "12345678-1234-1234-1234-123456789012"}
    with mock_sysfs(files):
        disk = DiskEntry(name="pmem0", devpath="/dev/pmem0")
        assert disk.serial == "12345678-1234-1234-1234-123456789012"


def test_pmem_prefers_serial_over_uuid(mock_sysfs):
    """Test that pmem devices prefer regular serial over UUID."""
    files = {
        "pmem0/device/serial": "PMEM_SERIAL",
        "pmem0/uuid": "12345678-1234-1234-1234-123456789012",
    }
    with mock_sysfs(files):
        disk = DiskEntry(name="pmem0", devpath="/dev/pmem0")
        assert disk.serial == "PMEM_SERIAL"


def test_pmem_prefers_vpd_over_uuid(mock_sysfs):
    """Test that pmem devices prefer VPD serial over UUID."""
    files = {
        "pmem0/device/vpd_pg80": b"\x00\x80\x00\x08PMEM_VPD",
        "pmem0/uuid": "12345678-1234-1234-1234-123456789012",
    }
    with mock_sysfs(files):
        disk = DiskEntry(name="pmem0", devpath="/dev/pmem0")
        assert disk.serial == "PMEM_VPD"


def test_serial_cached_property(mock_sysfs):
    """Test that serial is only read once (cached_property)."""
    files = {"sda/device/serial": "ONCE_ONLY"}

    with mock_sysfs(files), count_opens() as opens:
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        _ = disk.serial      # first access
        _ = disk.serial      # second access (should hit cache)

        # The /device/serial file should be opened exactly once
        serial_path = next((k for k in opens if k.endswith("/device/serial")), None)
        assert serial_path is not None, "Serial file was never opened"
        assert opens[serial_path] == 1, f"Serial file was opened {opens[serial_path]} times, expected 1"


def test_serial_read_error_returns_none(mock_sysfs):
    """Test graceful handling when no serial sources exist."""
    # Create empty mock environment - no serial files
    with mock_sysfs({}):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        # Should return None when no serial sources exist
        assert disk.serial is None


def test_priority_order(mock_sysfs):
    """Test the priority order: device/serial > vpd_pg80 > uuid."""
    # Test 1: All three sources present
    files1 = {
        "sda/device/serial": "REGULAR",
        "sda/device/vpd_pg80": b"\x00\x80\x00\x04VPD0",
        "sda/uuid": "UUID-VALUE",
    }
    with mock_sysfs(files1):
        disk1 = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk1.serial == "REGULAR"

    # Test 2: Only VPD and UUID (use different disk name to avoid caching)
    files2 = {
        "sdb/device/vpd_pg80": b"\x00\x80\x00\x04VPD0",
        "sdb/uuid": "UUID-VALUE",
    }
    with mock_sysfs(files2):
        disk2 = DiskEntry(name="sdb", devpath="/dev/sdb")
        assert disk2.serial == "VPD0"

    # Test 3: Only UUID (use different disk name to avoid caching)
    files3 = {"sdc/uuid": "UUID-VALUE"}
    with mock_sysfs(files3):
        disk3 = DiskEntry(name="sdc", devpath="/dev/sdc")
        assert disk3.serial == "UUID-VALUE"
