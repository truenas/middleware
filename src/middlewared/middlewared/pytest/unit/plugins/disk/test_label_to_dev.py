import stat

import pytest

from middlewared.plugins.disk_.disk_info import DiskService


@pytest.mark.parametrize("label,dev,block_devices,symlinks", [
    # Normal label (by-partuuid)
    (
        "disk/by-partuuid/4a3469b8-4c2f-11ee-9e9d-ac1f6b0a9d32",
        "sda1",
        ["/dev/sda1"],
        [("/dev/disk/by-partuuid/4a3469b8-4c2f-11ee-9e9d-ac1f6b0a9d32", "/dev/sda1")],
    ),
    # Label is a whole device
    (
        "sda",
        "sda",
        ["/dev/sda"],
        [],
    ),
    # Label is a partition
    (
        "sda1",
        "sda1",
        ["/dev/sda1"],
        [],
    ),
    # Label does not exist
])
def test_label_to_dev(fs, label, dev, block_devices, symlinks):
    for block_device in block_devices:
        fs.create_file(block_device, stat.S_IFBLK)
    for source, target in symlinks:
        fs.create_symlink(source, target)

    assert DiskService(None).label_to_dev(label) == dev
