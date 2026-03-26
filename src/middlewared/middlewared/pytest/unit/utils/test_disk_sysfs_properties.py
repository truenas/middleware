r"""Test DiskEntry sysfs property reads strip trailing whitespace.

Regression guard for commit ed771bfa4a (NAS-140361): a refactor of
DiskEntry.__opener accidentally removed the .strip() call on sysfs file
reads.  Sysfs files include a trailing newline, so without .strip():

  - temp()          — hwmon name "drivetemp\n" fails the membership test
  - media_type      — "1\n" != "1" misclassifies every HDD as SSD
  - translation     — vendor "NVMe\n" != "NVMe" breaks SNTL detection
  - model / vendor / firmware_revision — all carry trailing newlines
"""
import builtins
import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from middlewared.utils.disks_.disk_class import DiskEntry, TempEntry


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_sysfs(tmp_path):
    """Build a temp /sys/block tree and transparently redirect DiskEntry I/O.

    Patches builtins.open, os.scandir and os.path.exists so that any
    access under /sys/block/ is served from *tmp_path*/sys/block/ instead.
    """
    @contextmanager
    def _mock(files: dict[str, bytes | str]):
        for rel_path, data in files.items():
            fpath = tmp_path / "sys" / "block" / rel_path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, (bytes, bytearray)):
                fpath.write_bytes(data)
            else:
                fpath.write_text(data)

        original_open = builtins.open
        original_scandir = os.scandir
        original_exists = os.path.exists

        def _redirect(path: str) -> str:
            """Return the tmp_path equivalent for /sys/block/ paths."""
            rel = str(path).split("/sys/block/", 1)[1]
            return str(tmp_path / "sys" / "block" / rel)

        def mock_open(path, mode="r", *args, **kwargs):
            if "/sys/block/" in str(path):
                return original_open(_redirect(path), mode, *args, **kwargs)
            return original_open(path, mode, *args, **kwargs)

        def mock_scandir(path):
            if "/sys/block/" in str(path):
                return original_scandir(_redirect(path))
            return original_scandir(path)

        def mock_exists(path):
            if "/sys/block/" in str(path):
                return original_exists(_redirect(path))
            return original_exists(path)

        with (
            patch("builtins.open", side_effect=mock_open),
            patch("os.scandir", side_effect=mock_scandir),
            patch("os.path.exists", side_effect=mock_exists),
        ):
            yield

    return _mock


# ---------------------------------------------------------------------------
# 1. __opener strip behaviour (using model as a proxy)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("QEMU HARDDISK\n", "QEMU HARDDISK"),
    ("value\r\n", "value"),
    ("  value  \n", "value"),
    ("value", "value"),
])
def test_opener_strips_whitespace(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/device/model": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").model == expected


def test_opener_returns_none_on_missing_file(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").model is None


# ---------------------------------------------------------------------------
# 2. media_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("1\n", "HDD"),
    ("0\n", "SSD"),
    ("1", "HDD"),
    ("0", "SSD"),
])
def test_media_type(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/queue/rotational": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").media_type == expected


def test_media_type_missing_defaults_to_ssd(mock_sysfs):
    """When the rotational file is absent __opener returns None, and
    None != '1' evaluates to SSD."""
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").media_type == "SSD"


def test_media_type_hdd_regression(mock_sysfs):
    r"""Regression: without .strip(), '1\n' != '1' caused every HDD
    to be misclassified as SSD."""
    with mock_sysfs({"sda/queue/rotational": "1\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").media_type == "HDD"


# ---------------------------------------------------------------------------
# 3. vendor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("ATA\n", "ATA"),
    ("NVMe\n", "NVMe"),
    ("ATA     \n", "ATA"),
    ("  SAMSUNG  \n", "SAMSUNG"),
])
def test_vendor(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/device/vendor": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").vendor == expected


def test_vendor_none_when_missing(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").vendor is None


# ---------------------------------------------------------------------------
# 4. model
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("QEMU HARDDISK\n", "QEMU HARDDISK"),
    ("Samsung SSD 970 EVO Plus\n", "Samsung SSD 970 EVO Plus"),
    ("  ST8000NM000A  \n", "ST8000NM000A"),
])
def test_model(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/device/model": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").model == expected


def test_model_none_when_missing(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").model is None


# ---------------------------------------------------------------------------
# 5. firmware_revision
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("SN04\n", "SN04"),
    ("  2.5+  \n", "2.5+"),
])
def test_firmware_revision_from_rev(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/device/rev": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").firmware_revision == expected


def test_firmware_revision_fallback_to_firmware_rev(mock_sysfs):
    with mock_sysfs({"sda/device/firmware_rev": "1.3.2\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").firmware_revision == "1.3.2"


def test_firmware_revision_prefers_rev(mock_sysfs):
    with mock_sysfs({"sda/device/rev": "SN04\n", "sda/device/firmware_rev": "OLD\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").firmware_revision == "SN04"


def test_firmware_revision_none_when_both_missing(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").firmware_revision is None


# ---------------------------------------------------------------------------
# 6. translation
# ---------------------------------------------------------------------------

def test_translation_satl(mock_sysfs):
    """vpd_pg89 present -> SATL."""
    with mock_sysfs({"sda/vpd_pg89": ""}):
        assert DiskEntry(name="sda", devpath="/dev/sda").translation == "SATL"


def test_translation_sntl(mock_sysfs):
    """sd* device with vendor NVMe -> SNTL."""
    with mock_sysfs({"sda/device/vendor": "NVMe\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").translation == "SNTL"


def test_translation_sntl_regression(mock_sysfs):
    r"""Regression: without .strip(), vendor reads as 'NVMe\n' which
    != 'NVMe', so SNTL is never detected for NVMe-behind-SAS."""
    with mock_sysfs({"sda/device/vendor": "NVMe\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").translation == "SNTL"


def test_translation_none_ata_vendor(mock_sysfs):
    with mock_sysfs({"sda/device/vendor": "ATA\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").translation is None


def test_translation_none_nvme_device(mock_sysfs):
    """NVMe vendor on an nvme* device is not translation."""
    with mock_sysfs({"nvme0n1/device/vendor": "NVMe\n"}):
        assert DiskEntry(name="nvme0n1", devpath="/dev/nvme0n1").translation is None


def test_translation_satl_priority_over_sntl(mock_sysfs):
    """When vpd_pg89 exists, SATL wins even if vendor is NVMe."""
    with mock_sysfs({"sda/vpd_pg89": "", "sda/device/vendor": "NVMe\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").translation == "SATL"


# ---------------------------------------------------------------------------
# 7. Numeric properties (lbs, pbs, size_sectors, size_bytes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("512\n", 512),
    ("4096\n", 4096),
    ("512", 512),
])
def test_lbs(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/queue/logical_block_size": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").lbs == expected


def test_lbs_fallback(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").lbs == 512


def test_lbs_non_numeric_fallback(mock_sysfs):
    with mock_sysfs({"sda/queue/logical_block_size": "invalid\n"}):
        assert DiskEntry(name="sda", devpath="/dev/sda").lbs == 512


@pytest.mark.parametrize("raw,expected", [
    ("512\n", 512),
    ("4096\n", 4096),
])
def test_pbs(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/queue/physical_block_size": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").pbs == expected


def test_pbs_fallback(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").pbs == 512


@pytest.mark.parametrize("raw,expected", [
    ("1953525168\n", 1953525168),
    ("0\n", 0),
])
def test_size_sectors(mock_sysfs, raw, expected):
    with mock_sysfs({"sda/size": raw}):
        assert DiskEntry(name="sda", devpath="/dev/sda").size_sectors == expected


def test_size_sectors_fallback(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").size_sectors == 0


def test_size_bytes(mock_sysfs):
    with mock_sysfs({"sda/size": "1953525168\n"}):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.size_bytes == 512 * 1953525168


# ---------------------------------------------------------------------------
# 8. temp()
# ---------------------------------------------------------------------------

def test_temp_drivetemp(mock_sysfs):
    with mock_sysfs({
        "sda/device/hwmon/hwmon0/name": "drivetemp\n",
        "sda/device/hwmon/hwmon0/temp1_input": "35000\n",
    }):
        result = DiskEntry(name="sda", devpath="/dev/sda").temp()
        assert result == TempEntry(temp_c=35.0, crit=None)


def test_temp_drivetemp_regression(mock_sysfs):
    r"""Regression: without .strip(), 'drivetemp\n' not in
    ('nvme', 'drivetemp') is True, so temperature is never read."""
    with mock_sysfs({
        "sda/device/hwmon/hwmon0/name": "drivetemp\n",
        "sda/device/hwmon/hwmon0/temp1_input": "45000\n",
    }):
        assert DiskEntry(name="sda", devpath="/dev/sda").temp().temp_c == 45.0


def test_temp_nvme(mock_sysfs):
    """NVMe scans device/ instead of device/hwmon/."""
    with mock_sysfs({
        "nvme0n1/device/hwmon0/name": "nvme\n",
        "nvme0n1/device/hwmon0/temp1_input": "42000\n",
        "nvme0n1/device/hwmon0/temp1_crit": "84000\n",
    }):
        result = DiskEntry(name="nvme0n1", devpath="/dev/nvme0n1").temp()
        assert result == TempEntry(temp_c=42.0, crit=84.0)


def test_temp_with_crit(mock_sysfs):
    with mock_sysfs({
        "sda/device/hwmon/hwmon0/name": "drivetemp\n",
        "sda/device/hwmon/hwmon0/temp1_input": "35000\n",
        "sda/device/hwmon/hwmon0/temp1_crit": "70000\n",
    }):
        result = DiskEntry(name="sda", devpath="/dev/sda").temp()
        assert result == TempEntry(temp_c=35.0, crit=70.0)


def test_temp_no_hwmon_dir(mock_sysfs):
    with mock_sysfs({}):
        assert DiskEntry(name="sda", devpath="/dev/sda").temp() == TempEntry(temp_c=None, crit=None)


def test_temp_wrong_hwmon_name_skipped(mock_sysfs):
    with mock_sysfs({
        "sda/device/hwmon/hwmon0/name": "coretemp\n",
        "sda/device/hwmon/hwmon0/temp1_input": "50000\n",
    }):
        assert DiskEntry(name="sda", devpath="/dev/sda").temp() == TempEntry(temp_c=None, crit=None)


def test_temp_multiple_hwmon_finds_correct(mock_sysfs):
    with mock_sysfs({
        "sda/device/hwmon/hwmon0/name": "coretemp\n",
        "sda/device/hwmon/hwmon0/temp1_input": "99000\n",
        "sda/device/hwmon/hwmon1/name": "drivetemp\n",
        "sda/device/hwmon/hwmon1/temp1_input": "35000\n",
    }):
        assert DiskEntry(name="sda", devpath="/dev/sda").temp().temp_c == 35.0


def test_temp_invalid_input(mock_sysfs):
    with mock_sysfs({
        "sda/device/hwmon/hwmon0/name": "drivetemp\n",
        "sda/device/hwmon/hwmon0/temp1_input": "not_a_number\n",
    }):
        assert DiskEntry(name="sda", devpath="/dev/sda").temp() == TempEntry(temp_c=None, crit=None)


# ---------------------------------------------------------------------------
# 9. Integration smoke test
# ---------------------------------------------------------------------------

def test_full_disk_sysfs_newlines(mock_sysfs):
    """All properties return clean values when sysfs files contain
    trailing newlines (real-world behaviour)."""
    with mock_sysfs({
        "sda/device/model": "QEMU HARDDISK\n",
        "sda/device/vendor": "ATA\n",
        "sda/device/rev": "2.5+\n",
        "sda/queue/rotational": "1\n",
        "sda/queue/logical_block_size": "512\n",
        "sda/queue/physical_block_size": "4096\n",
        "sda/size": "1953525168\n",
    }):
        disk = DiskEntry(name="sda", devpath="/dev/sda")
        assert disk.model == "QEMU HARDDISK"
        assert disk.vendor == "ATA"
        assert disk.firmware_revision == "2.5+"
        assert disk.media_type == "HDD"
        assert disk.lbs == 512
        assert disk.pbs == 4096
        assert disk.size_sectors == 1953525168
        assert disk.size_bytes == 512 * 1953525168
        assert disk.translation is None
