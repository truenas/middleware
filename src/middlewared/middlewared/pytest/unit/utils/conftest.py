import builtins
from contextlib import contextmanager
from unittest.mock import patch

import pytest


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

        def mock_open(path, mode="r", *args, **kwargs):
            if "/sys/block/" in str(path):
                # Extract relative path after /sys/block/
                rel_path = str(path).split("/sys/block/", 1)[1]
                test_path = tmp_path / "sys" / "block" / rel_path
                return original_open(str(test_path), mode, *args, **kwargs)
            return original_open(path, mode, *args, **kwargs)

        # Expose original handle for count_opens to use
        mock_open.__wrapped__ = original_open

        with patch("builtins.open", side_effect=mock_open):
            yield

    return _mock
